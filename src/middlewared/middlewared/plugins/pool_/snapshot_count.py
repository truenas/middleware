from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetSnapshotCountArgs,
    PoolDatasetSnapshotCountResult,
    ZFSResourceSnapshotCountQuery,
)
from middlewared.service import Service


class PoolDatasetService(Service):
    class Config:
        namespace = "pool.dataset"

    @api_method(
        PoolDatasetSnapshotCountArgs,
        PoolDatasetSnapshotCountResult,
        roles=["DATASET_READ"],
        check_annotations=True,
    )
    def snapshot_count(self, dataset: str) -> int:
        """Returns snapshot count for specified `dataset`."""
        return self.call_sync2(
            self.s.zfs.resource.snapshot.count_impl,
            ZFSResourceSnapshotCountQuery(paths=[dataset])
        )[dataset]
