from middlewared.schema import accepts, returns, Int, Str
from middlewared.service import Service


class PoolDatasetService(Service):

    class Config:
        namespace = "pool.dataset"

    @accepts(Str("dataset"))
    @returns(Int())
    def snapshot_count(self, dataset):
        """
        Returns snapshot count for specified `dataset`.
        """
        return self.middleware.call_sync("zfs.snapshot.count", [dataset])[dataset]
