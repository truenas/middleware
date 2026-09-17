from __future__ import annotations

from typing import TYPE_CHECKING, Any, overload

from middlewared.api import api_method
from middlewared.api.current import (
    QueryFilters,
    ZFSResourceCreateArgs,
    ZFSResourceCreateArgsData,
    ZFSResourceCreateResult,
    ZFSResourceDeleteArgs,
    ZFSResourceDeleteOptions,
    ZFSResourceDeleteResult,
    ZFSResourceDestroyArgs,
    ZFSResourceDestroyArgsData,
    ZFSResourceDestroyResult,
    ZFSResourceEntry,
    ZFSResourceQuery,
    ZFSResourceQueryArgs,
    ZFSResourceQueryOptions,
    ZFSResourceQueryOptionsCount,
    ZFSResourceQueryOptionsGet,
    ZFSResourceQueryResult,
)
from middlewared.service import CRUDService, private
from middlewared.service.decorators import pass_thread_local_storage
from middlewared.service_exception import InstanceNotFound

from . import resource_create as _create
from . import resource_destroy as _destroy
from . import resource_ops as _ops
from . import resource_query as _query
from .prefetch import ZFSResourcePoolPrefetchService
from .snapshot import ZFSResourceSnapshotService

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("ZFSResourceService",)


class ZFSResourceService(CRUDService[ZFSResourceEntry]):
    class Config:
        namespace = "zfs.resource"
        cli_private = True
        entry = ZFSResourceEntry
        role_prefix = "ZFS_RESOURCE"
        role_separate_delete = True
        event_send = False
        datastore_primary_key_type = "string"
        verbose_name = "ZFS resource"

    def __init__(self, middleware: Middleware):
        super().__init__(middleware)
        self.snapshot = ZFSResourceSnapshotService(middleware)
        self.pool = ZFSResourcePoolPrefetchService(middleware)

    @private
    def unlocked_zvols_fast(
        self,
        filters: list[list[Any]] | None = None,
        options: dict[str, Any] | None = None,
        additional_information: list[str] | None = None,
    ) -> list[dict[str, Any]] | dict[str, Any] | int:
        return _ops.unlocked_zvols_fast(self.context, filters, options, additional_information)

    @private
    @pass_thread_local_storage
    def promote(self, tls: Any, current_name: str) -> None:
        """
        Promote a ZFS clone to be independent of its origin snapshot.

        Args:
            current_name: The name of the zfs resource to be promoted.
        """
        _ops.promote(tls, current_name)

    @private
    @pass_thread_local_storage
    def mount(
        self,
        tls: Any,
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
    def rename(
        self,
        tls: Any,
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
        _ops.rename(tls, current_name, new_name, recursive, no_unmount, force_unmount)

    @private
    @pass_thread_local_storage
    def query_impl(self, tls: Any, data: ZFSResourceQuery) -> list[dict[str, Any]]:
        return _query.query_impl(self.context, tls, data)

    @private
    @pass_thread_local_storage
    def create_impl(self, tls: Any, data: ZFSResourceCreateArgsData) -> dict[str, Any]:
        return _create.create_impl(self.context, tls, data)

    @api_method(
        ZFSResourceCreateArgs,
        ZFSResourceCreateResult,
        check_annotations=True,
    )
    def do_create(self, data: ZFSResourceCreateArgsData) -> ZFSResourceEntry:
        """
        Create a ZFS resource (filesystem or volume) and mount it.

        Properties are given by native ZFS property name - exactly the names
        :method:`zfs.resource.query` returns - and are handed to ZFS as-is. The created
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
    def destroy_impl(
        self,
        tls: Any,
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
        return _destroy.destroy_impl(self.context, tls, path, recursive, all_snapshots, bypass, defer)

    @api_method(
        ZFSResourceDestroyArgs,
        ZFSResourceDestroyResult,
        roles=["ZFS_RESOURCE_DELETE"],
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

    @api_method(
        ZFSResourceDeleteArgs,
        ZFSResourceDeleteResult,
        check_annotations=True,
    )
    def do_delete(self, id_: str, options: ZFSResourceDeleteOptions) -> None:
        """
        Destroy the ZFS resource (filesystem or volume) named by ``id``.

        This is the CRUD spelling of :method:`zfs.resource.destroy` and enforces the same rules.

        To destroy snapshots, use :method:`zfs.resource.snapshot.destroy` instead.
        """
        _destroy.delete(self.context, id_, options)

    async def get_instance(self, id_: str, options: dict[str, Any] | None = None) -> ZFSResourceEntry:
        """
        Retrieve the ZFS resource named by ``id``, which may be any filesystem or volume, not only a pool
        root. An ``ENOENT`` error is raised when it does not exist or is an internal dataset.

        Only ``options.extra`` is honoured; every other query option would be meaningless for a single
        resource. See :method:`zfs.resource.query` for what ``extra`` accepts.
        """
        instance = await self.middleware.call(
            "zfs.resource.query",
            [["id", "=", id_]],
            {"extra": (options or {}).get("extra", {})},
        )
        if not instance:
            raise InstanceNotFound(f"{self._config.verbose_name} {id_} does not exist")

        return instance[0]  # type: ignore[no-any-return]

    @overload  # type: ignore[override]
    def query(  # type: ignore[overload-overlap]
        self, filters: QueryFilters, options: ZFSResourceQueryOptionsCount
    ) -> int: ...

    @overload
    def query(  # type: ignore[overload-overlap]
        self, filters: QueryFilters, options: ZFSResourceQueryOptionsGet
    ) -> ZFSResourceEntry: ...

    @overload
    def query(
        self, filters: QueryFilters, options: ZFSResourceQueryOptions = ...
    ) -> list[ZFSResourceEntry]: ...

    @api_method(
        ZFSResourceQueryArgs,
        ZFSResourceQueryResult,
        roles=["ZFS_RESOURCE_READ"],
        check_annotations=True,
    )
    def query(
        self, filters: QueryFilters, options: ZFSResourceQueryOptions = ZFSResourceQueryOptions()
    ) -> list[ZFSResourceEntry] | ZFSResourceEntry | int:
        """
        Query ZFS filesystems and volumes.

        .. important::
           Unlike every other query method, ``filters`` never widen what is walked. The
           dataset tree is traversed only as far as ``options.extra`` says; filters are
           then applied to what that traversal returned. With no ``extra`` the traversal
           is the pool roots only, so ``[["type", "=", "VOLUME"]]`` on its own returns an
           empty list even when volumes exist. Declare the scope you want first, for
           example ``{"extra": {"get_children": true}}`` for every dataset on the system
           or ``{"extra": {"paths": ["tank/foo"], "max_depth": 2}}`` for a subtree, and
           filter within it. This keeps the cost of a query explicit instead of letting a
           one-line filter walk every dataset on a large array.

        The one exception is an identity filter: ``[["id", "=", path]]``, ``[["name", "=", path]]``
        or the ``in`` form of either opens exactly those paths, without descending into
        children, regardless of ``extra.paths``, ``extra.get_children`` and ``extra.max_depth``.
        This is what makes :method:`zfs.resource.get_instance` cheap and correct for any dataset.
        Paths named this way never expose internal datasets; only paths listed in
        ``extra.paths`` do.

        Once the traversal is done, ``filters``, ``select``, ``order_by``, ``limit``, ``offset``,
        ``count`` and ``get`` behave exactly as they do on any other query method. A path listed in
        ``extra.paths`` that does not exist is skipped rather than reported as an error, so a query
        over a mixture of live and destroyed paths returns the ones that survived.

        Any ZFS property a filter or ``select`` refers to is fetched automatically, whether or not
        ``extra.properties`` lists it, and referring to ``properties.<name>.source`` turns
        ``extra.get_source`` on. A name that is not a ZFS property fails the query with ``EINVAL``
        instead of silently matching nothing. ``extra.properties`` itself is the default set of space
        properties when left as an empty list, and no properties at all when set to ``null``.

        ``extra.get_crypto``, ``extra.get_snapshot_count`` and ``extra.get_snapshots`` fill in
        ``crypto``, ``snapshot_count`` and ``snapshots``, which are ``null`` otherwise. The snapshot
        enrichments are read after the tree has been walked, so a resource destroyed in between
        carries ``null`` rather than failing the whole query.

        To query snapshots directly, use :method:`zfs.resource.snapshot.query` instead. A snapshot
        path in ``extra.paths`` is a validation error, as are overlapping paths when the traversal
        descends into children.

        Examples:

        Every dataset and volume on the system:

        .. code:: json

            [[], {"extra": {"get_children": true}}]

        One dataset by name:

        .. code:: json

            [[["id", "=", "tank/foo"]], {}]

        Every lz4-compressed dataset:

        .. code:: json

            [[["properties.compression.value", "=", "lz4"]], {"extra": {"get_children": true}}]
        """
        return self._handle_generic_query_result(
            _query.query(self.context, filters, options), options.count, options.get
        )
