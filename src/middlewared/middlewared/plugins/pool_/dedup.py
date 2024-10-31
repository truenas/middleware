from middlewared.api import api_method
from middlewared.api.current import DDTPrefetchArgs, DDTPrefetchResult, DDTPruneArgs, DDTPruneResult
from middlewared.service import job, Service


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'

    @api_method(DDTPruneArgs, DDTPruneResult)
    @job(lock=lambda args: f'ddt_prune_{args[0]["pool_name"]}')
    async def ddt_prune(self, job, options):
        """
        Prune DDT entries in pool `pool_name` based on the specified options.

        `percentage` is the percentage of DDT entries to prune.

        `days` is the number of days to prune DDT entries.
        """
        return await self.middleware.call('zfs.pool.ddt_prune', options)

    @api_method(DDTPrefetchArgs, DDTPrefetchResult)
    @job(lock=lambda args: f'ddt_prefetch_{args[0]}')
    async def ddt_prefetch(self, job, pool_name):
        """
        Prefetch DDT entries in pool `pool_name`.
        """
        return await self.middleware.call('zfs.pool.ddt_prefetch', pool_name)


async def pool_post_import(middleware, pool):
    if pool:
        middleware.logger.info('Prefetching ddt table of %r pool', pool['name'])
        middleware.create_task(middleware.call('zfs.pool.ddt_prefetch', pool['name']))
    else:
        # This is to handle the case when pools are imported on boot time when pool attr is none
        middleware.create_task(middleware.call('zfs.pool.ddt_prefetch_pools'))


async def setup(middleware):
    middleware.register_hook('pool.post_import', pool_post_import)
