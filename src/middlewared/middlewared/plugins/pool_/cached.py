from middlewared.service import filterable, filter_list, private, Service


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'

    CACHE = None

    @private
    @filterable
    async def query_cached(self, filters, options):
        cache = self.CACHE
        if cache is None:
            cache = self.CACHE = await self.middleware.call('pool.query')

        return filter_list(cache, filters, options)

    @private
    async def reset_query_cache(self):
        self.CACHE = None
