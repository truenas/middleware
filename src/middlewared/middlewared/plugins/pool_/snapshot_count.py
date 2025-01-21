from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetSnapshotCountArgs,
    PoolDatasetSnapshotCountResults,
)
from middlewared.service import Service


class PoolDatasetService(Service):
    class Config:
        namespace = "pool.dataset"

    @api_method(
        PoolDatasetSnapshotCountArgs,
        PoolDatasetSnapshotCountResults,
        roles=["DATASET_READ"],
    )
    def snapshot_count(self, dataset):
        """Returns snapshot count for specified `dataset`."""
        return self.middleware.call_sync("zfs.snapshot.count", [dataset])[dataset]
