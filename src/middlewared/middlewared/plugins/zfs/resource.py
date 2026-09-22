from __future__ import annotations

# Methods named after builtins shadow them within the class body, so annotations after such a method
# must qualify the type through `builtins` to refer to the type rather than the method.
import builtins
from typing import TYPE_CHECKING, Any

from middlewared.api import api_method
from middlewared.api.current import (
    PoolProcess,
    ZFSResourceChecksumChoicesArgs,
    ZFSResourceChecksumChoicesResult,
    ZFSResourceCompressionChoicesArgs,
    ZFSResourceCompressionChoicesResult,
    ZFSResourceCreateArgs,
    ZFSResourceCreateArgsData,
    ZFSResourceCreateResult,
    ZFSResourceDestroyArgs,
    ZFSResourceDestroyArgsData,
    ZFSResourceDestroyResult,
    ZFSResourceEntry,
    ZFSResourceListArgs,
    ZFSResourceListResult,
    ZFSResourceProcessesArgs,
    ZFSResourceProcessesResult,
    ZFSResourcePromoteArgs,
    ZFSResourcePromoteArgsData,
    ZFSResourcePromoteResult,
    ZFSResourceQuery,
    ZFSResourceQueryArgs,
    ZFSResourceQueryResult,
    ZFSResourceRecommendedZvolBlocksizeArgs,
    ZFSResourceRecommendedZvolBlocksizeResult,
    ZFSResourceRecordsizeChoicesArgs,
    ZFSResourceRecordsizeChoicesResult,
    ZFSResourceRenameArgs,
    ZFSResourceRenameArgsData,
    ZFSResourceRenameResult,
    ZFSResourceSetArgs,
    ZFSResourceSetArgsData,
    ZFSResourceSetResult,
)
from middlewared.service import Service, private
from middlewared.service.decorators import pass_thread_local_storage

from . import resource_create as _create
from . import resource_destroy as _destroy
from . import resource_info as _info
from . import resource_ops as _ops
from . import resource_processes as _processes
from . import resource_query as _query
from . import resource_set as _set
from .prefetch import ZFSResourcePoolPrefetchService
from .snapshot import ZFSResourceSnapshotService, audit_target

if TYPE_CHECKING:
    from collections.abc import Iterable

    from middlewared.main import Middleware

__all__ = ("ZFSResourceService",)


def _audit_set(data: dict[str, Any]) -> str:
    names = sorted(
        {k for k, v in (data.get("properties") or {}).items() if v is not None}
        | set(data.get("user_properties") or {})
        | set(data.get("inherit") or [])
    )
    return f"{data.get('path')} ({', '.join(names)})"


class ZFSResourceService(Service):
    class Config:
        namespace = "zfs.resource"
        cli_private = True
        entry = ZFSResourceEntry

    def __init__(self, middleware: Middleware):
        super().__init__(middleware)
        self.snapshot = ZFSResourceSnapshotService(middleware)
        self.pool = ZFSResourcePoolPrefetchService(middleware)

    @api_method(
        ZFSResourceListArgs,
        ZFSResourceListResult,
        roles=["ZFS_RESOURCE_READ"],
        check_annotations=True,
    )
    def list(self, data: ZFSResourceQuery) -> builtins.list[ZFSResourceEntry]:
        """
        List ZFS resources (datasets and volumes) with flexible filtering options.

        To query snapshots, use :method:`zfs.resource.snapshot.query` instead.

        A validation error is raised when:

        - a snapshot path is supplied (use :method:`zfs.resource.snapshot.query`)
        - overlapping paths are supplied with ``get_children`` enabled or ``max_depth`` greater than 0

        Examples:

        List all resources with default properties:

        .. code:: json

            {}

        List specific resources:

        .. code:: json

            {"paths": ["tank/documents", "tank/media"]}

        List specific properties with children:

        .. code:: json

            {"paths": ["tank"], "properties": ["mounted", "compression", "used"], "get_children": true}

        Get a hierarchical view of resources:

        .. code:: json

            {"paths": ["tank"], "nest_results": true, "get_children": true}
        """
        return _query.list_resources(self.context, data)

    @api_method(
        ZFSResourceQueryArgs,
        ZFSResourceQueryResult,
        roles=["ZFS_RESOURCE_READ"],
        check_annotations=True,
        removed_in="v27",
    )
    def query(self, data: ZFSResourceQuery) -> builtins.list[ZFSResourceEntry]:
        """
        List ZFS resources (datasets and volumes) with flexible filtering options.
        """
        return _query.list_resources(self.context, data)

    @api_method(
        ZFSResourceChecksumChoicesArgs,
        ZFSResourceChecksumChoicesResult,
        roles=["ZFS_RESOURCE_READ"],
        check_annotations=True,
    )
    async def checksum_choices(self) -> dict[str, str]:
        """
        Retrieve the checksum algorithms a ZFS resource may use.
        """
        return _info.checksum_choices()

    @api_method(
        ZFSResourceCompressionChoicesArgs,
        ZFSResourceCompressionChoicesResult,
        roles=["ZFS_RESOURCE_READ"],
        check_annotations=True,
    )
    async def compression_choices(self) -> dict[str, str]:
        """
        Retrieve the compression algorithms a ZFS resource may use.
        """
        return _info.compression_choices()

    @api_method(
        ZFSResourceRecordsizeChoicesArgs,
        ZFSResourceRecordsizeChoicesResult,
        roles=["ZFS_RESOURCE_READ"],
        check_annotations=True,
    )
    def recordsize_choices(self, pool_name: str | None) -> builtins.list[str]:
        """
        Retrieve the record sizes a filesystem may be given.

        The upper bound is the running kernel's ``zfs_max_recordsize``. Naming a pool narrows the lower
        bound too, since a dRAID pool needs a minimum of 128K to avoid wasting space on padding.
        """
        return _info.recordsize_choices(self.context, pool_name)

    @api_method(
        ZFSResourceRecommendedZvolBlocksizeArgs,
        ZFSResourceRecommendedZvolBlocksizeResult,
        roles=["ZFS_RESOURCE_READ"],
        check_annotations=True,
    )
    def recommended_zvol_blocksize(self, pool: str) -> str:
        """
        Retrieve the recommended ``volblocksize`` for a new volume on the given pool.

        The recommendation follows the widest data vdev of the pool, so a pool created with mismatched
        vdev geometry is sized for its largest one.

        Get the block size for pool "tank":

        .. code:: json

            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "zfs.resource.recommended_zvol_blocksize",
                "params": ["tank"]
            }
        """
        return _info.recommended_zvol_blocksize(self.context, pool)

    @api_method(
        ZFSResourceProcessesArgs,
        ZFSResourceProcessesResult,
        roles=["ZFS_RESOURCE_READ"],
        check_annotations=True,
    )
    def processes(self, path: str) -> builtins.list[PoolProcess]:
        """
        Retrieve the processes holding open files on the ZFS resource named by ``path``.

        A locked resource reports no processes, since nothing can have its contents open. An ``ENOENT``
        error is raised when the resource does not exist.
        """
        return _processes.processes(self.context, path)

    @private
    async def kill_processes(self, oid: str, control_services: bool, max_tries: int = 5) -> None:
        await _processes.kill_processes(self.context, oid, control_services, max_tries)

    @private
    def processes_using_paths(
        self,
        paths: builtins.list[str],
        include_paths: bool = False,
        include_middleware: bool = False,
        devices: builtins.list[int] | None = None,
    ) -> builtins.list[dict[str, Any]]:
        return _processes.processes_using_paths(self.context, paths, include_paths, include_middleware, devices)

    @private
    def unlocked_zvols_fast(
        self,
        filters: builtins.list[builtins.list[Any]] | None = None,
        options: dict[str, Any] | None = None,
        additional_information: builtins.list[str] | None = None,
    ) -> builtins.list[dict[str, Any]] | dict[str, Any] | int:
        return _ops.unlocked_zvols_fast(self.context, filters, options, additional_information)

    @private
    @pass_thread_local_storage
    def promote_impl(self, tls: Any, data: ZFSResourcePromoteArgsData) -> None:
        _ops.promote_impl(tls, data)

    @api_method(
        ZFSResourcePromoteArgs,
        ZFSResourcePromoteResult,
        roles=["ZFS_RESOURCE_WRITE"],
        audit="ZFS resource promote",
        audit_extended=lambda data: data.get("path"),
        check_annotations=True,
    )
    def promote(self, data: ZFSResourcePromoteArgsData) -> None:
        """
        Promote a cloned ZFS resource so that it no longer depends on the snapshot it was cloned from.

        The origin snapshot and every snapshot older than it move to the promoted resource, which makes the
        resource it was cloned from the dependent one instead. This is how a clone is made destroyable
        independently of its origin.

        A validation error is raised when the resource does not exist (``ENOENT``), is not a clone
        (``EINVAL``) or is a protected path (``EACCES``).

        Example:

        .. code:: json

            {"path": "tank/clone"}
        """
        _ops.promote(self.context, data)

    @private
    @pass_thread_local_storage
    def mount(
        self,
        tls: Any,
        filesystem: str,
        mountpoint: str | None = None,
        recursive: bool = False,
        mount_options: builtins.list[str] | None = None,
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
        _ops.mount(tls, filesystem, mountpoint, recursive, mount_options, force, load_encryption_key)

    @private
    @pass_thread_local_storage
    def unmount(
        self,
        tls: Any,
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
        _ops.unmount(tls, filesystem, mountpoint, recursive, force, lazy, unload_encryption_key)

    @private
    @pass_thread_local_storage
    def unload_key(self, tls: Any, filesystem: str, recursive: bool = False, force_unmount: bool = False) -> None:
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
        _ops.unload_key(tls, filesystem, recursive, force_unmount)

    @private
    @pass_thread_local_storage
    def rename_impl(self, tls: Any, data: ZFSResourceRenameArgsData) -> None:
        _ops.rename_impl(tls, data)

    @api_method(
        ZFSResourceRenameArgs,
        ZFSResourceRenameResult,
        roles=["ZFS_RESOURCE_WRITE"],
        audit="ZFS resource rename from",
        audit_extended=lambda data: f"{data.get('current_name')!r} to {data.get('new_name')!r}",
        check_annotations=True,
    )
    def rename(self, data: ZFSResourceRenameArgsData) -> None:
        """
        Rename a ZFS resource (filesystem or volume), remounting it at its new location.

        To rename snapshots, use :method:`zfs.resource.snapshot.rename` instead. A dataset rename can never
        be recursive; renaming a resource renames its descendants along with it.

        .. warning::

            No check is made whether the resource is in use. If it is used by services such as SMB, iSCSI,
            snapshot tasks, replication, or cloud sync, renaming it may cause disruptions or service
            failures. Proceed only if you are certain the resource is not in use.

        A validation error is raised when:

        - a snapshot path (containing ``@``) is supplied
        - the resource does not exist (``ENOENT``)
        - the new name is already taken (``EEXIST``)
        - either name is a protected path (``EACCES``)

        Example:

        .. code:: json

            {"current_name": "tank/documents", "new_name": "tank/archive"}
        """
        _ops.rename(self.context, data)

    @private
    @pass_thread_local_storage
    def list_impl(self, tls: Any, data: ZFSResourceQuery) -> builtins.list[dict[str, Any]]:
        return _query.list_impl(self.context, tls, data)

    @private
    @pass_thread_local_storage
    def create_impl(self, tls: Any, data: ZFSResourceCreateArgsData) -> dict[str, Any]:
        return _create.create_impl(self.context, tls, data)

    @api_method(
        ZFSResourceCreateArgs,
        ZFSResourceCreateResult,
        roles=["ZFS_RESOURCE_WRITE"],
        audit="ZFS resource create",
        audit_extended=lambda data: data.get("path"),
        check_annotations=True,
    )
    def create(self, data: ZFSResourceCreateArgsData) -> ZFSResourceEntry:
        """
        Create a ZFS resource (filesystem or volume) and mount it.

        Properties are given by native ZFS property name - exactly the names
        :method:`zfs.resource.list` returns - and are handed to ZFS as-is. The created
        resource is re-queried after creation and returned, so the entry reflects the
        values as canonicalized by ZFS, not the input.

        To create snapshots, use :method:`zfs.resource.snapshot.create` instead.

        A validation error is raised when:

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
        - deduplication is requested on a system that is not entitled to it - licensed
          systems must carry the DEDUP feature (``EINVAL``)
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
            encryption key must be loaded (unlocked) or the creation fails with
            ``EACCES``.

        .. note::

            Hex keys (provided or generated) are stored by the system and may be
            retrieved with :method:`pool.dataset.export_key`; passphrases are never
            stored.
        """
        return _create.create(self.context, data)

    @private
    @pass_thread_local_storage
    def set_impl(
        self,
        tls: Any,
        path: str,
        properties: dict[str, Any] | None = None,
        user_properties: dict[str, str] | None = None,
        inherit: Iterable[str] | None = None,
        bypass: bool = False,
    ) -> None:
        """
        Set native properties, set user properties and inherit properties, in that order, on one open handle.

        Names are handed to ZFS as given; the public ``set`` validates the vocabulary. ``bypass`` lets internal
        callers write to protected paths and is never exposed to the public API. A change to ``mountpoint`` or a
        native share property remounts the filesystem, the library's default for ``set_properties``. Inheriting a
        user property removes it.
        """
        _set.set_impl(tls, path, properties, user_properties, inherit, bypass)

    @api_method(
        ZFSResourceSetArgs,
        ZFSResourceSetResult,
        roles=["ZFS_RESOURCE_WRITE"],
        audit="ZFS resource set",
        audit_extended=_audit_set,
        check_annotations=True,
    )
    def set(self, data: ZFSResourceSetArgsData) -> ZFSResourceEntry:
        """
        Change the properties of a ZFS resource (filesystem or volume).

        One request sets native properties, sets user properties and resets properties to their inherited
        value. Properties are given by native ZFS property name - exactly the names
        :method:`zfs.resource.list` returns - and are handed to ZFS as-is. The resource is re-queried
        afterwards and returned with the properties that were touched, so the entry reflects the values as
        canonicalized by ZFS, not the input.

        Inheriting a user property removes it. Inheriting ``acltype`` also inherits ``aclmode`` and
        ``aclinherit`` unless the request sets them, and setting ``acltype`` defaults them the way
        :method:`zfs.resource.create` does.

        A validation error is raised when:

        - a snapshot path (containing ``@``) is supplied (``EINVAL``)
        - the path references a protected internal resource (``EACCES``)
        - the resource does not exist (``ENOENT``)
        - nothing is set or inherited (``EINVAL``)
        - the same name is both set and inherited (``EINVAL``)
        - a name in ``inherit`` is neither a settable native property nor a user property name with a
          colon, or a user property name lacks a colon (``EINVAL``)
        - ``volsize`` is smaller than the volume's current size (``EINVAL``)
        - the effective ``acltype`` and ``aclmode`` combination is unusable - a posix or off acltype requires
          a discard aclmode and a discard aclmode may not be combined with the nfsv4 acltype (``EINVAL``)
        - ``special_small_blocks`` is set or inherited while ZFS tiering is enabled - placement is managed
          with :method:`zfs.tier.dataset_set_tier` (``EINVAL``)
        - deduplication is requested on a system that is not entitled to it, or for a filesystem whose data
          is placed on the SPECIAL vdev (the PERFORMANCE tier) while ZFS tiering is enabled (``EINVAL``)
        - a property is invalid for the resource type, is read-only, or has an invalid value (``EINVAL``)

        Examples:

        Set a property:

        .. code:: json

            {"path": "tank/documents", "properties": {"compression": "zstd"}}

        Reset a property to its inherited value:

        .. code:: json

            {"path": "tank/documents", "inherit": ["compression"]}

        Set one user property and remove another:

        .. code:: json

            {
                "path": "tank/documents",
                "user_properties": {"org.truenas:custom": "value"},
                "inherit": ["org.truenas:obsolete"]
            }
        """
        return _set.set(self.context, data)

    @private
    @pass_thread_local_storage
    def destroy_impl(
        self,
        tls: Any,
        path: str,
        recursive: bool = False,
        all_snapshots: bool = False,
        bypass: bool = False,
        defer: bool = False,
    ) -> None:
        """
        Internal implementation for destroying a ZFS resource.

        Raises `ZFSDestroyFailedException` when the destroy itself fails.

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
        _destroy.destroy_impl(self.context, tls, path, recursive, all_snapshots, bypass, defer)

    @api_method(
        ZFSResourceDestroyArgs,
        ZFSResourceDestroyResult,
        roles=["ZFS_RESOURCE_DELETE"],
        audit="ZFS resource destroy",
        audit_extended=lambda data: audit_target(data.get("path"), data, "recursive"),
        check_annotations=True,
    )
    def destroy(self, data: ZFSResourceDestroyArgsData) -> None:
        """
        Destroy a ZFS resource (filesystem or volume), optionally recursing into its descendants.

        To destroy snapshots, use
        :method:`zfs.resource.snapshot.destroy` instead.

        A validation error is raised when:

        - a snapshot path (containing ``@``) is supplied
          (use :method:`zfs.resource.snapshot.destroy`)
        - the resource does not exist (``ENOENT``)
        - the resource has children and ``recursive`` is ``false`` (``EBUSY``)
        - the resource has snapshots and ``recursive`` is ``false``
        - the target is the pool's root filesystem
        - the path is absolute or ends with ``/``
        - the path references a protected internal resource

        Examples:

        Destroy a single filesystem:

        .. code:: json

            {"path": "tank/temp"}

        Recursively destroy a filesystem and all of its descendants:

        .. code:: json

            {"path": "tank/parent", "recursive": true}

        .. note::

            - Root filesystem destruction is not allowed for safety
            - Protected system paths cannot be destroyed via API
            - Datasets with snapshots require ``recursive`` to be ``true``
        """
        _destroy.destroy(self.context, data)
