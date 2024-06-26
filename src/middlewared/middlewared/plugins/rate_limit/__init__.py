from middlewared.service import periodic, Service
from middlewared.utils.rate_limit.cache import RateLimitCache

CLEAR_CACHE_INTERVAL = 600


class RateLimitService(Service):

    class Config:
        namespace = 'rate.limit'
        private = True
        cli_private = True

    @periodic(interval=CLEAR_CACHE_INTERVAL, run_on_start=False)
    async def cache_clear(self):
        """Clear the entirety of the rate limit global cache."""
        # This is useful, mostly, for the edge-case scenario where
        # we have bad actor(s) that spam the API endpoints that
        # require no authentication and they are using random IP
        # addresses for each request. In that scenario, we will
        # store a maximum of amount of entries in the cache and
        # then refuse to honor any more requests for all consumers.
        # This is required for STIG purposes.
        await RateLimitCache.cache_clear()

    async def cache_get(self):
        """Return the global rate limit cache."""
        return await RateLimitCache.cache_get()

    async def cache_pop(self, method_name: str, ip: str) -> None:
        """Pop an entry from the global cache."""
        return await RateLimitCache.cache_pop(method_name, ip)
