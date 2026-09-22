from __future__ import annotations

from typing import Any

from middlewared.api import api_method
from middlewared.api.current import (
    ZFSResourceSnapshotCloneArgs,
    ZFSResourceSnapshotCloneQuery,
    ZFSResourceSnapshotCloneResult,
    ZFSResourceSnapshotCountArgs,
    ZFSResourceSnapshotCountQuery,
    ZFSResourceSnapshotCountResult,
    ZFSResourceSnapshotCreateArgs,
    ZFSResourceSnapshotCreateQuery,
    ZFSResourceSnapshotCreateResult,
    ZFSResourceSnapshotDestroyArgs,
    ZFSResourceSnapshotDestroyQuery,
    ZFSResourceSnapshotDestroyResult,
    ZFSResourceSnapshotEntry,
    ZFSResourceSnapshotHoldArgs,
    ZFSResourceSnapshotHoldQuery,
    ZFSResourceSnapshotHoldResult,
    ZFSResourceSnapshotHoldsArgs,
    ZFSResourceSnapshotHoldsQuery,
    ZFSResourceSnapshotHoldsResult,
    ZFSResourceSnapshotQuery,
    ZFSResourceSnapshotQueryArgs,
    ZFSResourceSnapshotQueryResult,
    ZFSResourceSnapshotReleaseArgs,
    ZFSResourceSnapshotReleaseQuery,
    ZFSResourceSnapshotReleaseResult,
    ZFSResourceSnapshotRenameArgs,
    ZFSResourceSnapshotRenameQuery,
    ZFSResourceSnapshotRenameResult,
    ZFSResourceSnapshotRollbackArgs,
    ZFSResourceSnapshotRollbackQuery,
    ZFSResourceSnapshotRollbackResult,
)
from middlewared.service import Service, private
from middlewared.service.decorators import pass_thread_local_storage

from . import snapshot_ops as _ops
from .snapshot_count_impl import count_snapshots_impl

__all__ = ("ZFSResourceSnapshotService",)


class ZFSResourceSnapshotService(Service):
    class Config:
        namespace = "zfs.resource.snapshot"
        cli_private = True
        entry = ZFSResourceSnapshotEntry

    @private
    @pass_thread_local_storage
    def query_impl(self, tls: Any, data: ZFSResourceSnapshotQuery) -> list[dict[str, Any]]:
        return _ops.query_impl(tls, data)

    @api_method(
        ZFSResourceSnapshotQueryArgs,
        ZFSResourceSnapshotQueryResult,
        roles=["SNAPSHOT_READ"],
        check_annotations=True,
    )
    def query(self, data: ZFSResourceSnapshotQuery) -> list[ZFSResourceSnapshotEntry]:
        """
        Retrieve information about ZFS snapshots, including their properties and user properties.

        Examples:

        Query all snapshots:

        .. code:: json

            {}

        Query snapshots for a specific dataset:

        .. code:: json

            {"paths": ["tank/data"]}

        Query a specific snapshot:

        .. code:: json

            {"paths": ["tank/data@backup"]}

        Query with recursion and specific properties:

        .. code:: json

            {"paths": ["tank"], "recursive": true, "properties": ["used", "referenced", "creation"]}
        """
        return _ops.query(self.context, data)

    @private
    def exists(self, snap_name: str) -> bool:
        return _ops.exists(self.context, snap_name)

    @private
    @pass_thread_local_storage
    def count_impl(self, tls: Any, data: ZFSResourceSnapshotCountQuery) -> dict[str, int]:
        return count_snapshots_impl(tls, data)

    @api_method(
        ZFSResourceSnapshotCountArgs,
        ZFSResourceSnapshotCountResult,
        roles=["SNAPSHOT_READ"],
        check_annotations=True,
    )
    def count(self, data: ZFSResourceSnapshotCountQuery) -> dict[str, int]:
        """
        Count ZFS snapshots per dataset.

        This method provides a fast way to count snapshots without retrieving full snapshot
        information. Useful for UI displays and quota checks.

        Examples:

        Count snapshots for root filesystems only:

        .. code:: json

            {}

        Count all snapshots recursively:

        .. code:: json

            {"recursive": true}

        Count snapshots for a specific dataset:

        .. code:: json

            {"paths": ["tank/data"]}

        Count snapshots for a dataset and all of its children:

        .. code:: json

            {"paths": ["tank"], "recursive": true}
        """
        return _ops.count(self.context, data)

    @private
    @pass_thread_local_storage
    def destroy_impl(self, tls: Any, data: ZFSResourceSnapshotDestroyQuery) -> None:
        _ops.destroy_impl(tls, data)

    @api_method(
        ZFSResourceSnapshotDestroyArgs,
        ZFSResourceSnapshotDestroyResult,
        roles=["SNAPSHOT_DELETE"],
        check_annotations=True,
    )
    def destroy(self, data: ZFSResourceSnapshotDestroyQuery) -> None:
        """
        Destroy ZFS snapshots.

        A validation error is raised when:

        - the snapshot does not exist (``ENOENT``)
        - it has dependent clones and ``defer`` is ``false`` (``EBUSY``)
        - it has active holds (``EBUSY``)
        - a protected path is targeted without ``bypass`` (``EACCES``)

        Examples:

        Destroy a single snapshot:

        .. code:: json

            {"path": "tank/data@backup"}

        Destroy matching snapshots in child datasets:

        .. code:: json

            {"path": "tank@backup", "recursive": true}

        Defer destruction if the snapshot is in use:

        .. code:: json

            {"path": "tank/data@snap", "defer": true}

        Destroy all snapshots of a dataset:

        .. code:: json

            {"path": "tank/data", "all_snapshots": true}

        Destroy all snapshots of a dataset and its children:

        .. code:: json

            {"path": "tank", "all_snapshots": true, "recursive": true}
        """
        _ops.destroy(self.context, data)

    @private
    @pass_thread_local_storage
    def rename_impl(self, tls: Any, data: ZFSResourceSnapshotRenameQuery) -> None:
        return _ops.rename_impl(tls, data)

    @api_method(
        ZFSResourceSnapshotRenameArgs,
        ZFSResourceSnapshotRenameResult,
        roles=["SNAPSHOT_WRITE"],
        check_annotations=True,
    )
    def rename(self, data: ZFSResourceSnapshotRenameQuery) -> None:
        """
        Rename a ZFS snapshot.

        A validation error is raised when:

        - the snapshot does not exist
        - the new name already exists
        - a supplied path is invalid

        Examples:

        Rename a single snapshot:

        .. code:: json

            {"current_name": "tank/data@old", "new_name": "tank/data@new"}

        Rename matching snapshots in child datasets:

        .. code:: json

            {"current_name": "tank@old", "new_name": "tank@new", "recursive": true}
        """
        _ops.rename(self.context, data)

    @private
    @pass_thread_local_storage
    def clone_impl(self, tls: Any, data: ZFSResourceSnapshotCloneQuery) -> bool:
        return _ops.clone_impl(self.context, tls, data)

    @api_method(
        ZFSResourceSnapshotCloneArgs,
        ZFSResourceSnapshotCloneResult,
        roles=["SNAPSHOT_WRITE"],
        check_annotations=True,
    )
    def clone(self, data: ZFSResourceSnapshotCloneQuery) -> None:
        """
        Clone a ZFS snapshot to create a new dataset.

        A validation error is raised when:

        - the source snapshot does not exist
        - the destination dataset already exists
        - the source is not a snapshot

        Examples:

        Clone a snapshot to a new dataset:

        .. code:: json

            {"snapshot": "tank/data@backup", "dataset": "tank/data_clone"}

        Clone with properties:

        .. code:: json

            {
                "snapshot": "tank/data@backup",
                "dataset": "tank/data_clone",
                "properties": {"compression": "lz4", "quota": "10G"}
            }
        """
        _ops.clone(self.context, data)

    @private
    @pass_thread_local_storage
    def create_impl(self, tls: Any, data: ZFSResourceSnapshotCreateQuery) -> Any:
        return _ops.create_impl(tls, data)

    @api_method(
        ZFSResourceSnapshotCreateArgs,
        ZFSResourceSnapshotCreateResult,
        roles=["SNAPSHOT_WRITE"],
        check_annotations=True,
    )
    def create(self, data: ZFSResourceSnapshotCreateQuery) -> ZFSResourceSnapshotEntry:
        """
        Create a ZFS snapshot.

        A validation error is raised when:

        - the dataset does not exist
        - the snapshot already exists

        Examples:

        Create a single snapshot:

        .. code:: json

            {"dataset": "tank/data", "name": "backup"}

        Create snapshots recursively:

        .. code:: json

            {"dataset": "tank", "name": "backup", "recursive": true}

        Create with user properties:

        .. code:: json

            {"dataset": "tank/data", "name": "backup", "user_properties": {"com.company:backup_type": "daily"}}
        """
        return _ops.create(self.context, data)

    @private
    @pass_thread_local_storage
    def hold_impl(self, tls: Any, data: ZFSResourceSnapshotHoldQuery) -> None:
        return _ops.hold_impl(tls, data)

    @api_method(
        ZFSResourceSnapshotHoldArgs,
        ZFSResourceSnapshotHoldResult,
        roles=["SNAPSHOT_WRITE"],
        check_annotations=True,
    )
    def hold(self, data: ZFSResourceSnapshotHoldQuery) -> None:
        """
        Create a hold on a ZFS snapshot.

        A hold prevents a snapshot from being destroyed. Multiple holds can be placed on a
        snapshot with different tags.

        A validation error is raised when:

        - the snapshot does not exist
        - the hold cannot be created

        Examples:

        Hold a snapshot:

        .. code:: json

            {"path": "tank/data@backup"}

        Hold with a custom tag:

        .. code:: json

            {"path": "tank/data@backup", "tag": "replication"}

        Hold matching snapshots in child datasets:

        .. code:: json

            {"path": "tank@backup", "recursive": true}
        """
        _ops.hold(self.context, data)

    @private
    @pass_thread_local_storage
    def holds_impl(self, tls: Any, path: str) -> tuple[str, ...]:
        return _ops.holds_impl(tls, path)

    @api_method(
        ZFSResourceSnapshotHoldsArgs,
        ZFSResourceSnapshotHoldsResult,
        roles=["SNAPSHOT_READ"],
        check_annotations=True,
    )
    def holds(self, data: ZFSResourceSnapshotHoldsQuery) -> list[str]:
        """
        Get holds on a ZFS snapshot.

        Examples:

        Get the holds on a snapshot:

        .. code:: json

            {"path": "tank/data@backup"}
        """
        return _ops.holds(self.context, data)

    @private
    @pass_thread_local_storage
    def release_impl(self, tls: Any, data: ZFSResourceSnapshotReleaseQuery) -> None:
        return _ops.release_impl(tls, data)

    @api_method(
        ZFSResourceSnapshotReleaseArgs,
        ZFSResourceSnapshotReleaseResult,
        roles=["SNAPSHOT_WRITE"],
        check_annotations=True,
    )
    def release(self, data: ZFSResourceSnapshotReleaseQuery) -> None:
        """
        Release hold(s) from a ZFS snapshot.

        A validation error is raised when:

        - the snapshot does not exist
        - the hold cannot be released

        Examples:

        Release a specific hold:

        .. code:: json

            {"path": "tank/data@backup", "tag": "replication"}

        Release all holds from a snapshot:

        .. code:: json

            {"path": "tank/data@backup"}

        Release a hold from matching snapshots in child datasets:

        .. code:: json

            {"path": "tank@backup", "tag": "backup", "recursive": true}
        """
        _ops.release(self.context, data)

    @private
    @pass_thread_local_storage
    def rollback_impl(self, tls: Any, data: ZFSResourceSnapshotRollbackQuery) -> None:
        return _ops.rollback_impl(tls, data)

    @api_method(
        ZFSResourceSnapshotRollbackArgs,
        ZFSResourceSnapshotRollbackResult,
        roles=["SNAPSHOT_WRITE"],
        check_annotations=True,
    )
    def rollback(self, data: ZFSResourceSnapshotRollbackQuery) -> None:
        """
        Rollback a ZFS dataset to a snapshot.

        .. warning::

            This is a destructive change. All data written since the target snapshot was
            taken will be discarded.

        A validation error is raised when:

        - the snapshot, or a child's snapshot, does not exist (errno ``ENOENT``)
        - ``path`` is not a snapshot path (errno ``EINVAL``)
        - snapshots more recent than ``path`` exist and neither ``recursive`` nor
          ``recursive_clones`` was passed (errno ``EINVAL``)
        - ``path`` is a protected path and the call did not come from the middleware itself
          (errno ``EACCES``)

        The call fails when:

        - a snapshot that has to be destroyed first has holds, or has clones and
          ``recursive_clones`` was not passed (errno ``EBUSY``); release a hold with
          :method:`zfs.resource.snapshot.release`
        - a destroy or the rollback itself fails, with the errno the kernel reported

        Examples:

        Roll back to a snapshot:

        .. code:: json

            {"path": "tank/data@backup"}

        Roll back, destroying more recent snapshots:

        .. code:: json

            {"path": "tank/data@backup", "recursive": true}

        Roll back all child datasets:

        .. code:: json

            {"path": "tank@backup", "recursive_rollback": true}
        """
        _ops.rollback(self.context, data)
