import errno
import os
import pathlib
import typing

import truenas_pylibzfs

from middlewared.api import api_method
from middlewared.api.current import (
    ZFSResourceCreateArgs,
    ZFSResourceCreateArgsData,
    ZFSResourceCreateResult,
    ZFSResourceDestroyArgs,
    ZFSResourceDestroyArgsData,
    ZFSResourceDestroyResult,
    ZFSResourceEntry,
    ZFSResourceQuery,
    ZFSResourceQueryArgs,
    ZFSResourceQueryResult,
    ZFSResourceSnapshotCountQuery,
)
from middlewared.plugins.zfs.snapshot_crud import ZFSResourceSnapshotService
from middlewared.service import Service, private
from middlewared.service.decorators import pass_thread_local_storage
from middlewared.service_exception import CallError, ValidationError
from middlewared.utils.filter_list import filter_list

from .create_impl import ZFS_INVALID_INPUT_ERRORS, create_impl
from .create_rules import (
    CreateContext,
    ancestor_chain,
    apply_draid_recordsize,
    apply_draid_volblocksize,
    apply_tier_snap,
    apply_volume_ssb_pin,
    check_acl_combination,
    check_dedup_tiering,
    # check_dedup_entitlement,  TODO uncomment when the truenas.entitlements API is merged
    check_encryption,
    check_name_valid,
    check_parent_not_readonly,
    check_path_shape,
    check_protected_path,
    check_tier_managed_ssb,
    check_user_property_names,
    check_volume_capacity,
    check_volume_has_volsize,
    resolve_create_request,
)
from .destroy_impl import destroy_impl
from .object_count_impl import estimate_object_count_impl
from .exceptions import (
    ZFSPathAlreadyExistsException,
    ZFSPathHasClonesException,
    ZFSPathHasHoldsException,
    ZFSPathInvalidException,
    ZFSPathNotASnapshotException,
    ZFSPathNotFoundException,
    ZFSPathNotProvidedException,
)
from .load_unload_impl import unload_key_impl
from .mount_unmount_impl import (
    mount_impl,
    unmount_impl,
)
from .query_impl import query_impl
from .rename_promote_clone_impl import (
    promote_impl,
    rename_impl,
)
from .utils import group_paths_by_parents, has_internal_path
from .zvol_utils import get_zvol_attachments_impl, unlocked_zvols_fast_impl

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


class ZFSResourceService(Service):
    class Config:
        namespace = "zfs.resource"
        cli_private = True
        entry = ZFSResourceEntry

    def __init__(self, middleware: "Middleware"):
        super().__init__(middleware)
        self.snapshot = ZFSResourceSnapshotService(middleware)

    @private
    def unlocked_zvols_fast(
        self,
        filters: list[list[typing.Any]] | None = None,
        options: dict[str, typing.Any] | None = None,
        additional_information: list[str] | None = None,
    ) -> list[dict[str, typing.Any]] | dict[str, typing.Any] | int:
        if filters is None:
            filters = list()
        if options is None:
            options = dict()
        if additional_information is None:
            additional_information = list()

        att_data = dict()
        if "ATTACHMENT" in additional_information:
            att_data = {"attachments": get_zvol_attachments_impl(self.middleware)}

        return filter_list(
            list(unlocked_zvols_fast_impl(additional_information, att_data).values()),
            filters,
            options,
        )

    @private
    @pass_thread_local_storage
    def estimate_object_count(self, tls: typing.Any, dataset_name: str) -> int:
        """Estimate total objects in a ZFS dataset using quota accounting.

        Returns 0 if the estimate is unavailable.
        """
        return estimate_object_count_impl(tls, dataset_name)

    @private
    @pass_thread_local_storage
    def promote(self, tls: typing.Any, current_name: str) -> None:
        """
        Promote a ZFS clone to be independent of its origin snapshot.

        Args:
            current_name: The name of the zfs resource to be promoted.
        """
        schema = "zfs.resource.promote"
        try:
            promote_impl(tls, current_name)
        except ZFSPathInvalidException:
            raise ValidationError(schema, f"{current_name!r} is ineligible for promotion.")
        except ZFSPathNotProvidedException:
            raise ValidationError(schema, "'current_name' key is required")
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)

    @private
    @pass_thread_local_storage
    def mount(
        self,
        tls: typing.Any,
        filesystem: str,
        mountpoint: str | None = None,
        recursive: bool = False,
        mount_options: list[str] | None = None,
        force: bool = False,
        load_encryption_key: bool = False,
    ) -> None:
        """
        Mount a ZFS filesystem.

        Args:
            filesystem: The zfs filesystem to be mounted.
            mountpoint: Optional parameter to manually specify the mountpoint at
                which to mount the datasets. If this is omitted then the
                mountpoint specied in the ZFS mountpoint property will be used.
                Generally the mountpoint should be not be specified and the
                library user should rely on the ZFS mountpoint property.
            recursive: Recursively mount all child filesystems. Default is False.
            mount_options: List of mount options to use when mounting the ZFS dataset.
                These may be any of MNTOPT constants in the truenas_pylibzfs.constants
                module. Defaults to None.

                NOTE: it's generally preferable to set these as ZFS properties rather
                than overriding via mount options
            force: Redacted datasets and ones with the `canmount` property set to off
                will fail to mount without explicitly passing the force option.
                Defaults to False.
            load_encryption_key: Load keys for encrypted filesystems as they are being mounted. This is
                equivalent to executing zfs load-key before mounting it. Defaults to False.
        """
        schema = "zfs.resource.mount"
        try:
            mount_impl(
                tls,
                filesystem,
                mountpoint,
                recursive,
                mount_options,
                force,
                load_encryption_key,
            )
        except ZFSPathNotProvidedException:
            raise ValidationError(schema, "'filesystem' key is required")
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)

    @private
    @pass_thread_local_storage
    def unmount(
        self,
        tls: typing.Any,
        filesystem: str,
        mountpoint: str | None = None,
        recursive: bool = False,
        force: bool = False,
        lazy: bool = False,
        unload_encryption_key: bool = False,
    ) -> None:
        """
        Unmount a ZFS filesystem.

        Args:
            filesystem: The zfs filesystem to be unmounted.
            mountpoint: Optional parameter to manually specify the mountpoint at
                which the dataset is mounted. This may be required for datasets with
                legacy mountpoints and is benefical if the mountpoint is known apriori.
            recursive: Unmount any children inheriting the mountpoint property.
            force: Forcefully unmount the file system, even if it is currently in use.
                Defaults to False.
            lazy: Perform a lazy unmount: make the mount unavailable for new accesses,
                immediately disconnect the filesystem and all filesystems mounted below
                it from each other and from the mount table, and actually perform the
                unmount when the mount ceases to be busy. Defaults to False.
            unload_encryption_key: Unload keys for any encryption roots unmounted by this operation.
                Defaults to False.
        """
        schema = "zfs.resource.unmount"
        try:
            unmount_impl(
                tls,
                filesystem,
                mountpoint,
                recursive,
                force,
                lazy,
                unload_encryption_key,
            )
        except ZFSPathNotProvidedException:
            raise ValidationError(schema, "'filesystem' key is required")
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)

    @private
    @pass_thread_local_storage
    def unload_key(
        self, tls: typing.Any, filesystem: str, recursive: bool = False, force_unmount: bool = False
    ) -> None:
        """
        Unload the encryption key from ZFS.

        Args:
            filesystem: Unload the encryption key from ZFS, removing the ability to access the
                resource (filesystem or zvol) and all of its children that inherit the
                'keylocation' property. This requires that the resource is not currently
                open or mounted.
            recursive: Recursively unload encryption keys for any child resources of the
                parent.
            force_unmount: Forcefully unmount the resource before unloading the encryption key.
        """
        schema = "zfs.resource.unload_key"
        try:
            unload_key_impl(tls, filesystem, recursive, force_unmount)
        except ZFSPathNotProvidedException:
            raise ValidationError(schema, "'filesystem' key is required")
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)

    @private
    @pass_thread_local_storage
    def rename(
        self,
        tls: typing.Any,
        current_name: str,
        new_name: str,
        recursive: bool = False,
        no_unmount: bool = False,
        force_unmount: bool = True,
    ) -> None:
        """
        Rename a ZFS resource.

        Args:
            current_name: The existing name of the zfs resource to be renamed.
            new_name: New name for ZFS object. The new name may not change the
                pool name component of the original name and contain
                alphanumeric characters and the following special characters:

                * Underscore (_)
                * Hyphen (-)
                * Colon (:)
                * Period (.)

                The name length may not exceed 255 bytes, but it is generally advisable
                to limit the length to something significantly less than the absolute
                name length limit.
            recursive: Recursively rename the snapshots of all descendant resources. Snapshots
                are the only resource that can be renamed recursively.
            no_unmount: Do not remount file systems during rename. If a filesystem's mountpoint
                property is set to legacy or none, the file system is not unmounted even
                if this option is False (default).
            force_unmount: Force unmount any file systems that need to be unmounted in the process.
        """
        schema = "zfs.resource.rename"
        if "@" in current_name:
            raise ValidationError(
                schema,
                "Use `zfs.resource.snapshot.rename` to rename snapshots.",
            )
        try:
            rename_impl(tls, current_name, new_name, recursive, no_unmount, force_unmount)
        except ZFSPathNotASnapshotException:
            raise ValidationError(schema, "recursive is only valid for snapshots")
        except ZFSPathAlreadyExistsException as e:
            raise ValidationError(schema, e.message, errno.EEXIST)
        except ZFSPathNotProvidedException:
            raise ValidationError(schema, "'current_name' key is required")
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)

    @private
    def validate_query_args(self, data: ZFSResourceQuery) -> None:
        for path in data.paths:
            if "@" in path:
                raise ValidationError(
                    "zfs.resource.query",
                    "Use `zfs.resource.snapshot.query` to query snapshot information.",
                )

        if data.get_children and group_paths_by_parents(data.paths):
            raise ValidationError(
                "zfs.resource.query",
                (
                    "Paths must be non-overlapping - no path can be relative to another "
                    "when get_children is set to True."
                ),
            )

    @private
    def nest_paths(self, flat_list: list[dict[str, typing.Any]]) -> list[dict[str, typing.Any]]:
        """
        Convert a flat list of dictionaries with path-like
        names into a nested tree structure. Nodes are attached
        to their nearest existing ancestor. If no ancestor
        exists, they become root nodes.

        Args:
            flat_list: List of dictionaries with, minimally, the
            following top-level keys 'name', 'pool', and 'children'.

        Returns:
            List containing the root nodes with nested children
        """
        node_map = {}
        roots = []
        # first pass is to create index
        for item in flat_list:
            node_map[item["name"]] = item
            if item["name"] == item["pool"]:
                # root filesystem (zpool)
                roots.append(item)
                continue

        # second pass establishes parent/child relationship
        # NOTE: the 2nd iteration is necessary
        # because the list being passed in is not
        # guaranteed to be in heirarchical order
        for item in flat_list:
            if item["name"] == item["pool"]:
                continue
            for parent in pathlib.PosixPath(item["name"]).parents:
                pap = parent.as_posix()
                if pap in node_map:
                    node_map[pap]["children"].append(item)
                    break
            else:
                # If no parent exists, this is a root
                roots.append(item)
        return roots

    @private
    @pass_thread_local_storage
    def query_impl(self, tls: typing.Any, data: ZFSResourceQuery) -> list[dict[str, typing.Any]]:
        self.validate_query_args(data)

        tier_enabled = False
        if data.get_tier:
            tier_enabled = self.call_sync2(self.s.zfs.tier.config).enabled

        results = query_impl(tls.lzh, data.model_dump(), tier_enabled=tier_enabled)
        if data.nest_results:
            return self.nest_paths(results)
        else:
            return results

    @private
    @pass_thread_local_storage
    def create_impl(self, tls: typing.Any, data: ZFSResourceCreateArgsData) -> dict[str, typing.Any]:
        """
        Internal implementation for creating a ZFS resource.

        Validates the path and properties, creates the resource (and any
        requested ancestors), mounts it, and returns the created resource
        re-queried from ZFS.
        """
        schema = "zfs.resource.create"
        path = data.path
        properties, encrypt = resolve_create_request(data)
        ctx = CreateContext(properties=properties, encrypt=encrypt)

        check_path_shape(data, ctx)
        check_protected_path(data, ctx)
        check_name_valid(data, ctx)
        check_user_property_names(data, ctx)

        ctx.tier_enabled = self.call_sync2(self.s.zfs.tier.config).enabled

        # one query serves the readonly, tier, acl, capacity and encryption
        # rules. Only the properties the rules below will read are requested.
        ancestor_props = ["readonly"]
        if data.type == "VOLUME":
            ancestor_props.extend(["available", "special_small_blocks"])
        else:
            if properties.acltype is not None or properties.aclmode is not None:
                ancestor_props.extend(["acltype", "aclmode"])
            if ctx.tier_enabled and data.properties.special_small_blocks is None:
                ancestor_props.extend(["special_small_blocks", "recordsize"])
        if data.encryption:
            ancestor_props.append("encryption")
        ctx.ancestors = {
            rv["name"]: rv
            for rv in self.call_sync2(
                self.s.zfs.resource.query_impl,
                ZFSResourceQuery(paths=ancestor_chain(path), properties=ancestor_props),
            )
        }

        check_parent_not_readonly(data, ctx)
        if ctx.tier_enabled:
            check_tier_managed_ssb(data, ctx)

        if data.type == "VOLUME":
            check_volume_has_volsize(data, ctx)
            apply_draid_volblocksize(self, data, ctx)
            if properties.special_small_blocks is None:
                apply_volume_ssb_pin(data, ctx)
            check_volume_capacity(data, ctx)
        else:
            if properties.recordsize is None:
                apply_draid_recordsize(self, data, ctx)
            if ctx.tier_enabled and properties.special_small_blocks is None:
                apply_tier_snap(data, ctx)
            if ctx.tier_enabled and str(properties.dedup or "off").lower() != "off":
                check_dedup_tiering(self, data, ctx)
            if properties.acltype is not None or properties.aclmode is not None:
                check_acl_combination(data, ctx)

        if data.encryption:
            check_encryption(data, ctx)

        # TODO uncomment when the truenas.entitlements API is merged
        # from truenas_pylicensed.features import LicenseFeature
        # if str(properties.dedup or "off").lower() != "off":
        #     ctx.dedup_entitled = self.call_sync2(self.s.truenas.entitlements.check, LicenseFeature.DEDUP).entitled
        #     check_dedup_entitlement(data, ctx)

        props = {k: v for k, v in properties.model_dump().items() if v is not None}
        try:
            create_impl(tls, path, data.type, props, data.user_properties, data.create_ancestors, encrypt)
        except truenas_pylibzfs.ZFSException as e:
            if e.code in ZFS_INVALID_INPUT_ERRORS:
                raise ValidationError(schema, str(e), errno.EINVAL)
            elif e.code == truenas_pylibzfs.ZFSError.EZFS_CRYPTOFAILED:
                raise CallError(
                    f"Failed to create {path!r}: the parent's encryption key is not "
                    "loaded. Unlock the parent dataset and try again.",
                    errno.EACCES,
                )
            raise CallError(f"Failed to create {path!r}: {e}")

        if encrypt:
            # Hex keys are stored by the system (passphrases deliberately are
            # not) so unlock/export/KMIP flows work; the post_create hook syncs
            # key material to the standby controller on HA systems. The
            # storage_encrypteddataset table remains the system of record for
            # dataset keys.
            self.middleware.call_sync(
                "pool.dataset.insert_or_update_encrypted_record",
                {"name": path, "encryption_key": encrypt["key"], "key_format": encrypt["keyformat"]},
            )
            self.middleware.call_hook_sync(
                "dataset.post_create",
                {
                    "encrypted": True,
                    "name": path,
                    "encryption_key": encrypt["key"],
                    "key_format": encrypt["keyformat"],
                },
            )

        requested = any(v is not None for v in data.properties.model_dump().values())
        report_props = list(props) if requested else []
        if encrypt:
            report_props.append("encryption")
        return self.call_sync2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(
                paths=[path],
                properties=report_props,
                get_user_properties=bool(data.user_properties),
            ),
        )[0]

    @api_method(
        ZFSResourceCreateArgs,
        ZFSResourceCreateResult,
        roles=["ZFS_RESOURCE_WRITE"],
        check_annotations=True,
    )
    def create(self, data: ZFSResourceCreateArgsData) -> ZFSResourceEntry:
        """
        Create a ZFS resource (filesystem or volume) and mount it.

        Properties are given by native ZFS property name - exactly the names
        :method:`zfs.resource.query` returns - and are handed to ZFS as-is. The created
        resource is re-queried after creation and returned, so the entry reflects the
        values as canonicalized by ZFS, not the input.

        To create snapshots, use :method:`zfs.resource.snapshot.create` instead.

        Invalid input is returned to the client as a JSON-RPC ``error`` response (code
        ``-32602``, *Invalid params*); each failing condition appears in the error's
        ``data.extra`` array with its own ``errno``. A validation error is raised when:

        - a snapshot path (containing ``@``) is supplied
          (use :method:`zfs.resource.snapshot.create`)
        - the resource already exists (``EEXIST``)
        - the pool, or the parent dataset when ``create_ancestors`` is ``false``, does
          not exist (``ENOENT``)
        - the target is a pool root filesystem, the path is absolute, ends with ``/``,
          or is not a valid ZFS name (``EINVAL``)
        - the path references a protected internal resource (``EACCES``)
        - a property outside the allowed creation set is supplied, or an allowed
          property is invalid for the resource type or has an invalid value
          (``EINVAL``)
        - an encryption or ZFS native sharing property is supplied through
          ``properties``, ``volsize`` is missing for a VOLUME, or a user property name
          lacks a colon (``EINVAL``)
        - ``encryption`` provides a hex key beneath a passphrase-encrypted parent, or
          would create an encryption root beneath an unencrypted dataset that itself
          sits inside an encrypted one (``EINVAL``)
        - a thick volume's reservation would consume more than 80% of the available
          space - create a sparse volume (``refreservation`` of ``none``) to
          deliberately oversubscribe (``EINVAL``)
        - the effective ``acltype`` and ``aclmode`` combination is unusable - a posix
          or off acltype requires a discard aclmode and a discard aclmode may not be
          combined with the nfsv4 acltype (``EINVAL``)
        - the nearest existing ancestor is readonly - the new filesystem could not be
          mounted beneath it (``EINVAL``)
        - ``special_small_blocks`` is supplied while ZFS tiering is enabled - placement
          is managed with :method:`zfs.tier.dataset_set_tier` (``EINVAL``)
        - deduplication is requested for a filesystem whose data would be placed on the
          SPECIAL vdev (the PERFORMANCE tier) while ZFS tiering is enabled (``EINVAL``)

        Examples:

        Create a filesystem:

        .. code:: json

            {"path": "tank/documents"}

        Create a filesystem with properties, creating missing ancestors:

        .. code:: json

            {
                "path": "tank/a/b/documents",
                "properties": {"compression": "lz4", "atime": "off"},
                "create_ancestors": true
            }

        Create a sparse 10GiB volume:

        .. code:: json

            {
                "path": "tank/vol1",
                "type": "VOLUME",
                "properties": {"volsize": 10737418240, "refreservation": "none"}
            }

        Create an encryption root with a generated key:

        .. code:: json

            {"path": "tank/secure", "encryption": {"generate_key": true}}

        Create an encryption root protected by a passphrase:

        .. code:: json

            {"path": "tank/private", "encryption": {"passphrase": "correct horse battery staple"}}

        .. note::

            Volumes are thick-provisioned by default (``refreservation`` defaults to
            the volsize, like ``zfs create -V``); set ``refreservation`` to ``none``
            for a sparse volume. Filesystems default ``xattr`` to ``sa``.

        .. note::

            A resource created under an encrypted parent inherits that encryption
            unless ``encryption`` makes it its own encryption root - an unencrypted
            child cannot be created beneath an encrypted parent. The parent's
            encryption key must be loaded (unlocked) or the creation fails with a
            JSON-RPC ``error`` response (code ``-32001``, *Method call error*, errno
            ``EACCES``).

        .. note::

            Hex keys (provided or generated) are stored by the system and may be
            retrieved with :method:`pool.dataset.export_key`; passphrases are never
            stored.
        """
        schema = "zfs.resource.create"
        try:
            return ZFSResourceEntry(**self.call_sync2(self.s.zfs.resource.create_impl, data))
        except ZFSPathAlreadyExistsException as e:
            raise ValidationError(schema, e.message, errno.EEXIST)
        except ZFSPathNotFoundException as e:
            missing = e.args[0]
            if "/" not in missing:
                msg = f"Pool {missing!r} does not exist."
            elif data.create_ancestors:
                msg = f"Parent dataset {missing!r} does not exist."
            else:
                msg = f"Parent dataset {missing!r} does not exist. Set create_ancestors to create it."
            raise ValidationError(schema, msg, errno.ENOENT)
        except ValueError as e:
            raise ValidationError(schema, str(e), errno.EINVAL)

    @private
    @pass_thread_local_storage
    def destroy_impl(
        self,
        tls: typing.Any,
        path: str,
        recursive: bool = False,
        all_snapshots: bool = False,
        bypass: bool = False,
        defer: bool = False,
    ) -> tuple[str | None, int | None]:
        """
        Internal implementation for destroying a ZFS resource.

        Args:
            path: The path of the zfs resource to destroy.
            recursive: Recursively destroy all descedants as well as
                release any holds and destroy any clones or snapshots.
            all_snapshots: If true, will delete all snapshots ONLY for the
                given zfs resource. Will not delete the resource itself.
            bypass: If true, will bypass the safety checks that prevent
                deleting zfs resources that are "protected".
                NOTE: This is only ever set by internal callers and is
                not exposed to the public API.
            defer: Rather than returning error if the given snapshot is ineligible for immediate destruction,
                mark it for deferred, automatic destruction once it becomes eligible.
        """
        schema = "zfs.resource.destroy"
        if os.path.isabs(path):
            raise ValidationError(
                schema,
                "Absolute path is invalid. Must be in form of <pool>/<resource>.",
                errno.EINVAL,
            )
        elif path.endswith("/"):
            raise ValidationError(schema, "Path must not end with a forward-slash.", errno.EINVAL)
        elif not bypass and has_internal_path(path):
            # NOTE: `bypass` is a value only exposed to
            # internal callers and not to our public API.
            raise ValidationError(schema, f"{path!r} is a protected path.", errno.EACCES)

        if "@" in path:
            raise ValidationError(
                schema,
                "Use `zfs.resource.snapshot.destroy` to destroy snapshots.",
            )

        tmp = path.split("/")
        if len(tmp) == 1 or tmp[-1] == "":
            raise ValidationError(schema, "Destroying the root filesystem is not allowed.", errno.EINVAL)

        if not recursive:
            rv = self.call_sync2(
                self.s.zfs.resource.query,
                ZFSResourceQuery(paths=[path], properties=None, get_children=True),
            )
            extra = "Set recursive=True to remove them."
            if not rv:
                raise ValidationError(schema, f"{path!r} does not exist.", errno.ENOENT)
            elif len(rv) > 1:
                raise ValidationError(schema, f"{path!r} has children. {extra}", errno.ENOTEMPTY)
            else:
                # Check if dataset has snapshots using snapshot.count
                snap_counts = self.call_sync2(
                    self.s.zfs.resource.snapshot.count,
                    ZFSResourceSnapshotCountQuery(paths=[path]),
                )
                if snap_counts.get(path, 0) > 0:
                    raise ValidationError(schema, f"{path!r} has snapshots. {extra}", errno.ENOTEMPTY)

        return destroy_impl(tls, path, recursive, all_snapshots, bypass, defer)

    @api_method(
        ZFSResourceDestroyArgs,
        ZFSResourceDestroyResult,
        roles=["ZFS_RESOURCE_DELETE"],
        check_annotations=True,
    )
    def destroy(self, data: ZFSResourceDestroyArgsData) -> None:
        """
        Destroy a ZFS resource (filesystem or volume).

        This method provides an interface for destroying ZFS datasets and volumes \
        with support for recursive deletion.

        NOTE: To destroy snapshots, use `zfs.resource.snapshot.destroy`.

        Args:
            data (dict): Dictionary containing destruction parameters:
                - path (str): Path of the ZFS resource to destroy. Must be in the form \
                    'pool/name' or 'pool/zvol'. Snapshot paths (containing '@') are \
                    not accepted - use `zfs.resource.snapshot.destroy` instead.
                    Cannot be an absolute path or end with a forward slash.
                - recursive (bool, optional): If True, recursively destroy all descendants \
                    including their snapshots, clones, and holds. Default: False.

        Returns:
            None: On successful destruction.

        Raises:
            ValidationError: Raised in the following cases:
                - Snapshot path provided (use zfs.resource.snapshot.destroy)
                - Resource does not exist (ENOENT)
                - Resource has children and recursive=False (EBUSY)
                - Resource has snapshots and recursive=False
                - Attempting to destroy root filesystem
                - Path is absolute (starts with /)
                - Path ends with forward slash
                - Path references protected internal resources

        Examples:
            # Destroy a simple filesystem
            destroy({"path": "tank/temp"})

            # Recursively destroy filesystem and all descendants
            destroy({"path": "tank/parent", "recursive": True})

        Notes:
            - Root filesystem destruction is not allowed for safety
            - Protected system paths cannot be destroyed via API
            - Datasets with snapshots require recursive=True
            - To destroy snapshots, use `zfs.resource.snapshot.destroy`
        """
        schema = "zfs.resource.destroy"
        path = data.path
        recursive = data.recursive
        try:
            failed, errnum = self.call_sync2(self.s.zfs.resource.destroy_impl, path, recursive)
        except ZFSPathHasClonesException as e:
            raise ValidationError(
                f"{schema}.defer",
                f"Snapshot {e.path!r} has dependent clones: {', '.join(e.clones)}",
                errno.ENOTEMPTY,
            )
        except ZFSPathHasHoldsException as e:
            raise ValidationError(schema, e.message, errno.ENOTEMPTY)
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)
        else:
            if failed:
                # this is the channel program execution path and so when an
                # error is raised while executing a channel program, the
                # handling of errors is done a bit differently since the
                # operation is done atomically behind the scenes. This should
                # only be happening if someone is recursively deleting a
                # resource.
                assert errnum is not None
                raise ValidationError(schema, failed, errnum)

    @api_method(
        ZFSResourceQueryArgs,
        ZFSResourceQueryResult,
        roles=["ZFS_RESOURCE_READ"],
        check_annotations=True,
    )
    def query(self, data: ZFSResourceQuery) -> list[ZFSResourceEntry]:
        """
        Query ZFS resources (datasets and volumes) with flexible filtering options.

        This method provides a high-performance interface for retrieving information \
        about ZFS resources, including their properties, hierarchical relationships, \
        and metadata. The query can be customized to retrieve specific resources, \
        properties, and control the output format.

        NOTE: To query snapshots, use `zfs.resource.snapshot.query`.

        Raises:
            ValidationError: If:
                - Snapshot paths are provided (use zfs.resource.snapshot.query)
                - Overlapping paths are provided with get_children=True

        Examples:
            # Query all resources with default properties
            query()

            # Query specific resources with all properties
            query({"paths": ["tank/documents", "tank/media"]})

            # Query with specific properties and children
            query({
                "paths": ["tank"],
                "properties": ["mounted", "compression", "used"],
                "get_children": True
            })

            # Get hierarchical view of resources
            query({"paths": ["tank"], "nest_results": True, "get_children": True})
        """
        try:
            return [ZFSResourceEntry(**resource) for resource in self.call_sync2(self.s.zfs.resource.query_impl, data)]
        except ZFSPathNotFoundException as e:
            raise ValidationError("zfs.resource.query", e.message, errno.ENOENT)
