from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetSnapshotCountArgs,
    PoolDatasetSnapshotCountResult,
)
from middlewared.service import Service


class PoolDatasetService(Service):
    class Config:
        namespace = "pool.dataset"

    @api_method(
        PoolDatasetSnapshotCountArgs,
        PoolDatasetSnapshotCountResult,
        roles=["DATASET_READ"],
    )
    def snapshot_count(self, dataset):
        """Returns snapshot count for specified `dataset`."""
        return self.middleware.call_sync("zfs.snapshot.count", [dataset])[dataset]
