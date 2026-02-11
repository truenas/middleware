from middlewared.api import api_method
from middlewared.api.current import (
    PoolDdtPruneArgs, PoolDdtPruneResult, PoolDdtPrefetchArgs, PoolDdtPrefetchResult, PoolPrefetchArgs,
    PoolPrefetchResult
)

from middlewared.service import job, Service


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'

    @api_method(PoolDdtPruneArgs, PoolDdtPruneResult, roles=['POOL_WRITE'])
    @job(lock=lambda args: f'ddt_prune_{args[0].get("pool_name")}')
    async def ddt_prune(self, job, options):
        """
        Prune DDT entries in pool `pool_name` based on the specified options.

        `percentage` is the percentage of DDT entries to prune.

        `days` is the number of days to prune DDT entries.
        """
        return await self.middleware.call('zfs.pool.ddt_prune', options)

    @api_method(PoolDdtPrefetchArgs, PoolDdtPrefetchResult, roles=['POOL_WRITE'], removed_in='v26')
    @job(lock=lambda args: f'ddt_prefetch_{args[0]}')
    async def ddt_prefetch(self, job, pool_name):
        """
        Prefetch DDT entries in pool `pool_name`.

        .. deprecated::
            Use `pool.prefetch` instead, which prefetches both DDT and BRT metadata.
        """
        return await self.middleware.call('zfs.resource.pool.prefetch', pool_name)

    @api_method(PoolPrefetchArgs, PoolPrefetchResult, roles=['POOL_WRITE'])
    @job(lock=lambda args: f'pool_prefetch_{args[0]}')
    async def prefetch(self, job, pool_name):
        """
        Prefetch pool metadata (DDT and BRT) into ARC.

        Loads both the Deduplication Table (DDT) and Block Reference Table (BRT)
        into the ARC to reduce latency of subsequent operations. This is useful
        for warming up the cache before performing operations that benefit from
        having this metadata readily available.

        The DDT tracks deduplication metadata, while the BRT tracks block cloning
        metadata used for efficient copy-on-write operations.
        """
        return await self.middleware.call('zfs.resource.pool.prefetch', pool_name)
