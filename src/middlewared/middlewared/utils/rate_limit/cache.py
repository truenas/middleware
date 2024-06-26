from asyncio import sleep
from dataclasses import dataclass
from random import uniform
from time import monotonic
from typing import TypedDict

from middlewared.auth import is_ha_connection
from middlewared.utils.origin import TCPIPOrigin

__all__ = ['RateLimitCache']


@dataclass(frozen=True)
class RateLimitConfig:
    """The maximum number of calls per unique consumer of the endpoint."""
    max_calls: int = 20
    """The maximum time in seconds that a unique consumer may request an
    endpoint that is being rate limited."""
    max_period: int = 60
    """The maximum number of unique entries the cache supports"""
    max_cache_entries: int = 100
    """The value used to separate the unique values when generating
    a unique key to be used to store the cached information."""
    separator: str = '_##_'
    """The starting decimal value for the time to be slept in the event
    rate limit thresholds for a particular consumer has been met."""
    sleep_start: float = 1.0
    """The ending decimal value for the time to be slept in the event
    rate limit thresholds for a particular consumer has been met."""
    sleep_end: float = 10.0


class RateLimitObject(TypedDict):
    """The number of times this method was called by the consumer."""
    num_times_called: int
    """The monotonic time representing when this particular cache
    entry was last reset."""
    last_reset: float


RL_CACHE: dict[str, RateLimitObject] = dict()


class RateLimit:
    def cache_key(self, method_name: str, ip: str) -> str:
        """Generate a unique key per endpoint/consumer"""
        return f'{method_name}{RateLimitConfig.separator}{ip}'

    def rate_limit_exceeded(self, method_name: str, ip: str) -> bool:
        """Return a boolean indicating if the total number of calls
        per unique endpoint/consumer has been reached."""
        key = self.cache_key(method_name, ip)
        try:
            now: float = monotonic()
            if RateLimitConfig.max_period - (now - RL_CACHE[key]['last_reset']) <= 0:
                # time window elapsed, so time to reset
                RL_CACHE[key]['num_times_called'] = 0
                RL_CACHE[key]['last_reset'] = now

            # always increment
            RL_CACHE[key]['num_times_called'] += 1
            return RL_CACHE[key]['num_times_called'] > RateLimitConfig.max_calls
        except KeyError:
            pass

        return False

    async def add(self, method_name: str, origin: TCPIPOrigin) -> str | None:
        """Add an entry to the cache. Returns the IP address of
        origin of the request if it has been cached, returns None otherwise"""
        if not isinstance(origin, TCPIPOrigin):
            return None

        ip, port = origin.addr, origin.port
        if any((ip is None, port is None)) or is_ha_connection(ip, port):
            # Short-circuit if:
            # 1. if the IP address is None
            # 2. OR the port is None
            # 3. OR the origin of the request is from our HA P2P heartbeat
            #   connection
            return None
        else:
            key = self.cache_key(method_name, ip)
            if key not in RL_CACHE:
                RL_CACHE[key] = RateLimitObject(num_times_called=0, last_reset=monotonic())
            return ip

    async def cache_pop(self, method_name: str, ip: str) -> None:
        """Pop (remove) an entry from the cache."""
        RL_CACHE.pop(self.cache_key(method_name, ip), None)

    async def cache_clear(self) -> None:
        """Clear all entries from the cache."""
        RL_CACHE.clear()

    async def random_sleep(self) -> None:
        """Sleep a random amount of seconds."""
        await sleep(round(uniform(RateLimitConfig.sleep_start, RateLimitConfig.sleep_end), 2))

    async def cache_get(self) -> RL_CACHE:
        """Return the global cache."""
        return RL_CACHE

    @property
    def max_entries_reached(self) -> bool:
        """Return a boolean indicating if the total number of entries
        in the global cache has reached `self.max_cache_entries`."""
        return len(RL_CACHE) == RateLimitConfig.max_cache_entries


RateLimitCache = RateLimit()
