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
        This method provides an interface for retrieving information about ZFS snapshots,
        including their properties and user properties.

        Args:
            data: Query parameters containing:
                - paths: List of dataset or snapshot paths to query. If empty, queries all.
                - properties: List of ZFS properties to retrieve. Empty list = defaults, None = none.
                - get_user_properties: Whether to include user-defined properties.
                - get_source: Whether to include property source information.
                - recursive: Include snapshots from child datasets.
                - min_txg: Minimum transaction group filter (0 = no minimum).
                - max_txg: Maximum transaction group filter (0 = no maximum).

        Returns:
            List of snapshot entries with requested properties.

        Examples:
            # Query all snapshots
            query({})

            # Query snapshots for a specific dataset
            query({"paths": ["tank/data"]})

            # Query a specific snapshot
            query({"paths": ["tank/data@backup"]})

            # Query with recursion and specific properties
            query({
                "paths": ["tank"],
                "recursive": True,
                "properties": ["used", "referenced", "creation"]
            })
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

        This method provides a fast way to count snapshots without retrieving
        full snapshot information. Useful for UI displays and quota checks.

        Args:
            data: Count parameters containing:
                - paths: List of dataset paths to count snapshots for. If empty,
                         counts snapshots for root filesystems only.
                - recursive: Include snapshots from child datasets in counts.

        Returns:
            Dict mapping dataset names to their snapshot counts.

        Examples:
            # Count snapshots for root filesystems only
            count({})

            # Count all snapshots recursively
            count({"recursive": True})

            # Count snapshots for a specific dataset
            count({"paths": ["tank/data"]})

            # Count snapshots for a dataset and all children
            count({"paths": ["tank"], "recursive": True})
        """
        return _ops.count(self.context, data)

    @private
    @pass_thread_local_storage
    def destroy_impl(self, tls: Any, data: ZFSResourceSnapshotDestroyQuery) -> tuple[str | None, int | None]:
        return _ops.destroy_impl(tls, data)

    @api_method(
        ZFSResourceSnapshotDestroyArgs,
        ZFSResourceSnapshotDestroyResult,
        roles=["SNAPSHOT_DELETE"],
        check_annotations=True,
    )
    def destroy(self, data: ZFSResourceSnapshotDestroyQuery) -> None:
        """
        Destroy ZFS snapshots.

        Args:
            data: Destroy parameters containing:
                - path: Snapshot path (e.g., 'pool/dataset@snapshot') or dataset path
                        when all_snapshots=True (e.g., 'pool/dataset').
                - recursive: Recursively destroy matching snapshots in child datasets.
                - all_snapshots: If True, path is a dataset and all its snapshots are destroyed.
                - defer: Defer destruction if snapshot is in use (e.g., has clones).

        Returns:
            None on success.

        Raises:
            ValidationError: If snapshot not found, has clones (without defer), or has holds.

        Examples:
            # Destroy a single snapshot
            destroy({"path": "tank/data@backup"})

            # Destroy recursively (all matching child snapshots)
            destroy({"path": "tank@backup", "recursive": True})

            # Defer destruction if in use
            destroy({"path": "tank/data@snap", "defer": True})

            # Destroy all snapshots for a dataset
            destroy({"path": "tank/data", "all_snapshots": True})

            # Destroy all snapshots for a dataset and its children
            destroy({"path": "tank", "all_snapshots": True, "recursive": True})
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

        Args:
            data: Rename parameters containing:
                - current_name: Current snapshot path (e.g., 'pool/dataset@old_name').
                - new_name: New snapshot path (e.g., 'pool/dataset@new_name').
                - recursive: Recursively rename matching snapshots in child datasets.

        Returns:
            None on success.

        Raises:
            ValidationError: If snapshot not found, new name already exists, or invalid paths.

        Examples:
            # Rename a single snapshot
            rename({"current_name": "tank/data@old", "new_name": "tank/data@new"})

            # Rename recursively (all matching child snapshots)
            rename({
                "current_name": "tank@old",
                "new_name": "tank@new",
                "recursive": True
            })
        """
        _ops.rename(self.context, data)

    @private
    @pass_thread_local_storage
    def clone_impl(self, tls: Any, data: ZFSResourceSnapshotCloneQuery) -> None:
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

        Args:
            data: Clone parameters containing:
                - snapshot: Source snapshot path to clone (e.g., 'pool/dataset@snapshot').
                - dataset: Destination dataset path for the clone (e.g., 'pool/clone').
                - properties: Optional ZFS properties to set on the cloned dataset.

        Returns:
            None on success.

        Raises:
            ValidationError: If snapshot not found, destination already exists, or source is not a snapshot.

        Examples:
            # Clone a snapshot to a new dataset
            clone({"snapshot": "tank/data@backup", "dataset": "tank/data_clone"})

            # Clone with properties
            clone({
                "snapshot": "tank/data@backup",
                "dataset": "tank/data_clone",
                "properties": {"compression": "lz4", "quota": "10G"}
            })
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

        Args:
            data: Create parameters containing:
                - dataset: Dataset path to snapshot (e.g., 'pool/dataset').
                - name: Snapshot name (the part after @).
                - recursive: Create snapshots recursively for child datasets.
                - exclude: Datasets to exclude when creating recursive snapshots.
                - user_properties: User properties to set on the snapshot.

        Returns:
            Snapshot entry for the created snapshot.

        Raises:
            ValidationError: If dataset not found or snapshot already exists.

        Examples:
            # Create a single snapshot
            create({"dataset": "tank/data", "name": "backup"})

            # Create recursive snapshots
            create({
                "dataset": "tank",
                "name": "backup",
                "recursive": True
            })

            # Create with user properties
            create({
                "dataset": "tank/data",
                "name": "backup",
                "user_properties": {"com.company:backup_type": "daily"}
            })
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

        A hold prevents a snapshot from being destroyed. Multiple holds
        can be placed on a snapshot with different tags.

        Args:
            data: Hold parameters containing:
                - path: Snapshot path to hold (e.g., 'pool/dataset@snapshot').
                - tag: Hold tag name (default: 'truenas').
                - recursive: Apply hold to matching snapshots in child datasets.

        Returns:
            None on success.

        Raises:
            ValidationError: If snapshot not found or hold creation fails.

        Examples:
            # Hold a single snapshot
            hold({"path": "tank/data@backup"})

            # Hold with custom tag
            hold({"path": "tank/data@backup", "tag": "replication"})

            # Hold recursively
            hold({"path": "tank@backup", "recursive": True})
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

        Args:
            data: Query parameters containing:
                - path: Snapshot path to query (e.g., 'pool/dataset@snapshot').

        Returns:
            List of hold tag names on the snapshot.

        Examples:
            holds({"path": "tank/data@backup"})
            # Returns: ["truenas", "replication"]
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

        Args:
            data: Release parameters containing:
                - path: Snapshot path to release holds from (e.g., 'pool/dataset@snapshot').
                - tag: Specific hold tag to release. If None, releases all holds.
                - recursive: Release holds from matching snapshots in child datasets.

        Returns:
            None on success.

        Raises:
            ValidationError: If snapshot not found or release fails.

        Examples:
            # Release a specific hold
            release({"path": "tank/data@backup", "tag": "replication"})

            # Release all holds from a snapshot
            release({"path": "tank/data@backup"})

            # Release holds recursively
            release({"path": "tank@backup", "tag": "backup", "recursive": True})
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

        WARNING: This is a destructive change. All data written since the
        target snapshot was taken will be discarded.

        Args:
            data: Rollback parameters containing:
                - path: Snapshot path to rollback to (e.g., 'pool/dataset@snapshot').
                - recursive: Destroy any snapshots more recent than the one specified.
                - recursive_clones: Like recursive, but also destroy any clones.
                - force: Force unmount of any clones.
                - recursive_rollback: Do a complete recursive rollback of each child snapshot.

        Returns:
            None on success.

        Raises:
            ValidationError: If `path` is not a snapshot path, the snapshot (or a child's snapshot)
                does not exist, snapshots more recent than `path` exist and neither `recursive` nor
                `recursive_clones` was passed, or `path` is protected.
            CallError: If a snapshot that has to be destroyed first has holds, or has clones and
                `recursive_clones` was not passed (errno EBUSY), or if a destroy or the rollback
                itself failed, with the errno the kernel reported.

        Examples:
            # Basic rollback
            rollback({"path": "tank/data@backup"})

            # Rollback destroying more recent snapshots
            rollback({"path": "tank/data@backup", "recursive": True})

            # Rollback all child datasets
            rollback({"path": "tank@backup", "recursive_rollback": True})
        """
        _ops.rollback(self.context, data)
