import errno
import os
import pathlib

from middlewared.api import api_method
from middlewared.api.current import (
    ZFSResourceDestroyArgs,
    ZFSResourceDestroyResult,
    ZFSResourceEntry,
    ZFSResourceQueryArgs,
    ZFSResourceQueryResult,
)
from middlewared.service import Service, private
from middlewared.service_exception import ValidationError
from middlewared.service.decorators import pass_thread_local_storage
from middlewared.utils.filter_list import filter_list

from .destroy_impl import destroy_impl
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


class ZFSResourceService(Service):
    class Config:
        namespace = "zfs.resource"
        cli_private = True
        entry = ZFSResourceEntry

    @private
    def unlocked_zvols_fast(
        self,
        filters: list | None = None,
        options: dict | None = None,
        additional_information: list | None = None,
    ):
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
    def promote(self, tls, current_name: str) -> None:
        """
        Promote a ZFS clone to be independent of its origin snapshot.

        Args:
            current_name: The name of the zfs resource to be promoted.
        """
        schema = "zfs.resource.promote"
        try:
            promote_impl(tls, current_name)
        except ZFSPathInvalidException:
            raise ValidationError(
                schema, f"{current_name!r} is ineligible for promotion."
            )
        except ZFSPathNotProvidedException:
            raise ValidationError(schema, "'current_name' key is required")
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)

    @private
    @pass_thread_local_storage
    def mount(
        self,
        tls,
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
        tls,
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
        self, tls, filesystem: str, recursive: bool = False, force_unmount: bool = False
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
        tls,
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
            rename_impl(
                tls, current_name, new_name, recursive, no_unmount, force_unmount
            )
        except ZFSPathNotASnapshotException:
            raise ValidationError(schema, "recursive is only valid for snapshots")
        except ZFSPathAlreadyExistsException as e:
            raise ValidationError(schema, e.message, errno.EEXIST)
        except ZFSPathNotProvidedException:
            raise ValidationError(schema, "'current_name' key is required")
        except ZFSPathNotFoundException as e:
            raise ValidationError(schema, e.message, errno.ENOENT)

    @private
    def validate_query_args(self, data):
        for path in data["paths"]:
            if "@" in path:
                raise ValidationError(
                    "zfs.resource.query",
                    "Use `zfs.resource.snapshot.query` to query snapshot information.",
                )

        if data["get_children"] and group_paths_by_parents(data["paths"]):
            raise ValidationError(
                "zfs.resource.query",
                (
                    "Paths must be non-overlapping - no path can be relative to another "
                    "when get_children is set to True."
                ),
            )

    @private
    def nest_paths(self, flat_list: dict) -> list[dict]:
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
    def query_impl(self, tls, data: dict | None = None):
        base = ZFSResourceQueryArgs().model_dump()["data"]
        if data is None:
            final = base
        else:
            final = base | data
            self.validate_query_args(final)

        results = query_impl(tls.lzh, final)
        if final["nest_results"]:
            return self.nest_paths(results)
        else:
            return results

    @private
    @pass_thread_local_storage
    def destroy_impl(
        self,
        tls,
        path: str,
        recursive: bool = False,
        all_snapshots: bool = False,
        bypass: bool = False,
        defer: bool = False,
    ):
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
            raise ValidationError(
                schema, "Path must not end with a forward-slash.", errno.EINVAL
            )
        elif not bypass and has_internal_path(path):
            # NOTE: `bypass` is a value only exposed to
            # internal callers and not to our public API.
            raise ValidationError(
                schema, f"{path!r} is a protected path.", errno.EACCES
            )

        if "@" in path:
            raise ValidationError(
                schema,
                "Use `zfs.resource.snapshot.destroy` to destroy snapshots.",
            )

        tmp = path.split("/")
        if len(tmp) == 1 or tmp[-1] == "":
            raise ValidationError(
                schema, "Destroying the root filesystem is not allowed.", errno.EINVAL
            )

        if not recursive:
            args = {"paths": [path], "properties": None, "get_children": True}
            rv = self.middleware.call_sync("zfs.resource.query", args)
            extra = "Set recursive=True to remove them."
            if not rv:
                raise ValidationError(schema, f"{path!r} does not exist.", errno.ENOENT)
            elif len(rv) > 1:
                raise ValidationError(
                    schema, f"{path!r} has children. {extra}", errno.ENOTEMPTY
                )
            else:
                # Check if dataset has snapshots using snapshot.count
                snap_counts = self.middleware.call_sync(
                    "zfs.resource.snapshot.count", {"paths": [path]}
                )
                if snap_counts.get(path, 0) > 0:
                    raise ValidationError(
                        schema, f"{path!r} has snapshots. {extra}", errno.ENOTEMPTY
                    )

        return destroy_impl(tls, path, recursive, all_snapshots, bypass, defer)

    @api_method(
        ZFSResourceDestroyArgs, ZFSResourceDestroyResult, roles=["ZFS_RESOURCE_WRITE"]
    )
    def destroy(self, data):
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
        path = data["path"]
        recursive = data.get("recursive", False)
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
                raise ValidationError(schema, failed, errnum)

    @api_method(
        ZFSResourceQueryArgs,
        ZFSResourceQueryResult,
        roles=["ZFS_RESOURCE_READ"],
    )
    def query(self, data):
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
            return self.middleware.call_sync("zfs.resource.query_impl", data)
        except ZFSPathNotFoundException as e:
            raise ValidationError("zfs.resource.query", e.message, errno.ENOENT)
