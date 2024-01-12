from middlewared.service import private, Service


class BootService(Service):

    CACHE = None

    @private
    async def query_cached(self):
        cache = self.CACHE
        if cache is None:
            boot_pool = await self.middleware.call("boot.pool_name")
            cache = self.CACHE = await self.middleware.call("zfs.pool.query", [["id", "=", boot_pool]])

        return cache

    @private
    async def reset_query_cache(self):
        self.CACHE = None
