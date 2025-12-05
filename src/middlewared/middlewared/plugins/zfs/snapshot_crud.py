import errno

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

from .exceptions import (
    ZFSPathNotFoundException,
)
from .snapshot_query_impl import query_snapshots_impl
from .utils import group_paths_by_parents


class ZFSResourceSnapshotService(Service):
    class Config:
        namespace = "zfs.resource.snapshot"
        cli_private = True
        entry = ZFSResourceSnapshotEntry

    @private
    def validate_query_args(self, data):
        """Validate query arguments.

        Validates that dataset paths don't overlap when recursive=True.
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
                "zfs.resource.snapshot.query",
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
        self.validate_query_args(data)
        try:
            return self.middleware.call_sync("zfs.resource.snapshot.query_impl", data)
        except ZFSPathNotFoundException as e:
            raise ValidationError(
                "zfs.resource.snapshot.query", e.message, errno.ENOENT
            )
