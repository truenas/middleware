from middlewared.api import api_method
from middlewared.api.current import PoolDatasetRecordsizeChoicesArgs, PoolDatasetRecordsizeChoicesResult
from middlewared.service import Service


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    # https://openzfs.github.io/openzfs-docs/Performance%20and%20Tuning/Module%20Parameters.html#zfs-max-recordsize
    # Maximum supported (at time of writing) is 16MB.
    MAPPING = [
        (1 << 9, '512'),
        (1 << 9, '512B'),
        (1 << 10, '1K'),
        (1 << 11, '2K'),
        (1 << 12, '4K'),
        (1 << 13, '8K'),
        (1 << 14, '16K'),
        (1 << 15, '32K'),
        (1 << 16, '64K'),
        (1 << 17, '128K'),
        (1 << 18, '256K'),
        (1 << 19, '512K'),
        (1 << 20, '1M'),
        (1 << 21, '2M'),
        (1 << 22, '4M'),
        (1 << 23, '8M'),
        (1 << 24, '16M'),
    ]

    @api_method(PoolDatasetRecordsizeChoicesArgs, PoolDatasetRecordsizeChoicesResult, roles=['DATASET_READ'])
    def recordsize_choices(self, pool_name):
        """
        Retrieve recordsize choices for datasets.
        """
        minimum_recordsize = self.MAPPING[0][0]
        if pool_name and self.middleware.call_sync('pool.is_draid_pool', pool_name):
                minimum_recordsize = 1 << 17  # We want minimum of 128k for dRAID pools

        with open('/sys/module/zfs/parameters/zfs_max_recordsize') as f:
            val = int(f.read().strip())
            return [v for k, v in self.MAPPING if minimum_recordsize <= k <= val]
