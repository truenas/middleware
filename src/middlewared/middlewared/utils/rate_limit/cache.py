from asyncio import sleep
from dataclasses import dataclass
from random import uniform
from threading import RLock
from time import monotonic

from middlewared.auth import is_ha_connection
from middlewared.utils.origin import TCPIPOrigin

__all__ = ('RateLimitCache')

"""The maximum number of calls per unique consumer of the endpoint."""
MAX_CALLS: int = 20
"""The maximum time in seconds that a unique consumer may request an
endpoint that is being rate limited."""
MAX_PERIOD: int = 60


@dataclass(slots=True, kw_only=True)
class RateLimitObject:
    """A per-{endpoint/consumer} re-entrant lock so that a
    global lock is not shared between all (potential)
    consumers hitting the same endpoint."""
    lock: RLock
    """The number of times this method was called by the consumer."""
    num_times_called: int = 0
    """The monotonic time representing when this particular cache
    entry was last reset."""
    last_reset: float = monotonic()


@dataclass(slots=True)
class RateLimitCachedObjects:
    """The maximum number of unique entries the cache supports"""
    MAX_CACHE_ENTRIES: int = 100
    """The value used to separate the unique values when generating
    a unique key to be used to store the cached information."""
    SEPARATOR: str = '_'
    """The global cache object used to store the information about
    all endpoints/consumers being rate limited."""
    CACHE: dict[str, RateLimitObject] = dict()
    """The starting decimal value for the time to be slept in the event
    rate limit thresholds for a particular consumer has been met."""
    RANDOM_START: float = 1.0
    """The ending decimal value for the time to be slept in the event
    rate limit thresholds for a particular consumer has been met."""
    RANDOM_END: float = 10.0

    @property
    def max_entries_reached(self) -> bool:
        """Return a boolean indicating if the total number of entries
        in the global cache has reached `self.MAX_CACHE_ENTRIES`."""
        return len(self.CACHE) == self.MAX_CACHE_ENTRIES

    def cache_key(self, method_name: str, ip: str) -> str:
        """Generate a unique key per endpoint/consumer"""
        return f'{method_name}{self.SEPARATOR}{ip}'

    def rate_limit_exceeded(self, method_name: str, ip: str) -> bool:
        """Return a boolean indicating if the total number of calls
        per unique endpoint/consumer has been reached."""
        key = self.cache_key(method_name, ip)
        try:
            with self.CACHE[key].lock:
                now: float = monotonic()
                if MAX_PERIOD - (now - self.CACHE[key].last_reset) <= 0:
                    # time window elapsed, so time to reset
                    self.CACHE[key].num_times_called = 0
                    self.CACHE[key].last_reset = now

                # always increment
                self.CACHE[key].num_times_called += 1
                return self.CACHE[key].num_times_called > MAX_CALLS
        except KeyError:
            pass

        return False

    def add(self, method_name: str, origin: TCPIPOrigin) -> str | None:
        """Add an entry to the cache. Returns the IP address of
        origin of the request if it has been cached, returns None otherwise"""
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
            if key not in self.CACHE:
                self.CACHE[key] = RateLimitObject(lock=RLock())
                return ip

            return None

    def pop(self, method_name: str, ip: str) -> None:
        """Pop (remove) an entry from the cache."""
        self.CACHE.pop(self.cache_key(method_name, ip), None)

    def clear(self) -> None:
        """Clear all entries from the cache."""
        self.CACHE.clear()

    @property
    def random_range(self) -> float:
        """Return a random float within self.RANDOM_START and self.RANDOM_END
        rounded to the 100th decimal point"""
        return round(uniform(self.RANDOM_START, self.RANDOM_END), 2)

    async def random_sleep(self) -> None:
        """Sleep a random amount of seconds within range of `self.random_range`."""
        await sleep(self.random_range)


RateLimitCache = RateLimitCachedObjects()
