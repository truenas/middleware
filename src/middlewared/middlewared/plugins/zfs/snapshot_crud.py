import errno
import os

from middlewared.api import api_method
from middlewared.api.current import (
    ZFSResourceSnapshotEntry,
    ZFSResourceSnapshotCountArgs,
    ZFSResourceSnapshotCountResult,
    ZFSResourceSnapshotCloneArgs,
    ZFSResourceSnapshotCloneResult,
    ZFSResourceSnapshotCreateArgs,
    ZFSResourceSnapshotCreateResult,
    ZFSResourceSnapshotDestroyArgs,
    ZFSResourceSnapshotDestroyResult,
    ZFSResourceSnapshotHoldArgs,
    ZFSResourceSnapshotHoldResult,
    ZFSResourceSnapshotQueryArgs,
    ZFSResourceSnapshotQueryResult,
    ZFSResourceSnapshotReleaseArgs,
    ZFSResourceSnapshotReleaseResult,
    ZFSResourceSnapshotRenameArgs,
    ZFSResourceSnapshotRenameResult,
    ZFSResourceSnapshotRollbackArgs,
    ZFSResourceSnapshotRollbackResult,
)
from middlewared.service import Service, private
from middlewared.service_exception import ValidationError
from middlewared.service.decorators import pass_thread_local_storage

from .destroy_impl import destroy_impl, DestroyArgs
from .exceptions import (
    ZFSPathHasClonesException,
    ZFSPathHasHoldsException,
    ZFSPathNotFoundException,
)
from .snapshot_count_impl import count_snapshots_impl
from .snapshot_query_impl import query_snapshots_impl
from .utils import group_paths_by_parents, has_internal_path


class ZFSResourceSnapshotService(Service):
    class Config:
        namespace = "zfs.resource.snapshot"
        cli_private = True
        entry = ZFSResourceSnapshotEntry

    @private
    def validate_recursive_paths(self, schema: str, data: dict):
        """Validate paths don't overlap when recursive=True.

        (Duplicate paths are already rejected by Pydantic UniqueList)
        """
        if not data.get("recursive", False):
            return

        # When recursive, check for overlapping dataset paths
        # (snapshot paths like "tank@snap" are direct lookups, not recursive)
        paths = data.get("paths", [])
        dataset_paths = [p for p in paths if "@" not in p]
        if group_paths_by_parents(dataset_paths):
            raise ValidationError(
                schema,
                (
                    "Paths must be non-overlapping - no path can be relative to another "
                    "when recursive is set to True."
                ),
            )

    @private
    @pass_thread_local_storage
    def query_impl(self, tls, data: dict | None = None):
        base = ZFSResourceSnapshotQueryArgs().model_dump()["data"]
        if data is None:
            final = base
        else:
            final = base | data

        return query_snapshots_impl(tls.lzh, final)

    @api_method(
        ZFSResourceSnapshotQueryArgs,
        ZFSResourceSnapshotQueryResult,
        roles=["SNAPSHOT_READ"],
    )
    def query(self, data):
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
        self.validate_recursive_paths("zfs.resource.snapshot.query", data)
        try:
            return self.middleware.call_sync("zfs.resource.snapshot.query_impl", data)
        except ZFSPathNotFoundException as e:
            raise ValidationError(
                "zfs.resource.snapshot.query", e.message, errno.ENOENT
            )

    @private
    @pass_thread_local_storage
    def count_impl(self, tls, data: dict | None = None):
        base = ZFSResourceSnapshotCountArgs().model_dump()["data"]
        if data is None:
            final = base
        else:
            final = base | data

        return count_snapshots_impl(tls.lzh, final)

    @api_method(
        ZFSResourceSnapshotCountArgs,
        ZFSResourceSnapshotCountResult,
        roles=["SNAPSHOT_READ"],
    )
    def count(self, data):
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
        self.validate_recursive_paths("zfs.resource.snapshot.count", data)
        try:
            return self.middleware.call_sync("zfs.resource.snapshot.count_impl", data)
        except ZFSPathNotFoundException as e:
            raise ValidationError(
                "zfs.resource.snapshot.count", e.message, errno.ENOENT
            )
