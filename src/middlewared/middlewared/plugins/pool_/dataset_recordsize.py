from middlewared.api import api_method
from middlewared.api.current import PoolDatasetRecordsizeChoicesArgs, PoolDatasetRecordsizeChoicesResult
from middlewared.service import Service


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @api_method(PoolDatasetRecordsizeChoicesArgs, PoolDatasetRecordsizeChoicesResult, roles=['DATASET_READ'])
    def recordsize_choices(self, pool_name):
        """
        Retrieve recordsize choices for datasets.
        """
        return self.call_sync2(self.s.zfs.resource.recordsize_choices, pool_name)
