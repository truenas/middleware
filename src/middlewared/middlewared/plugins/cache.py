from collections import namedtuple
from collections.abc import Callable
from time import monotonic
from typing import Any

from middlewared.service import Service


class CacheService(Service):
    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super(CacheService, self).__init__(*args, **kwargs)
        self.__cache = {}
        self.kv_tuple = namedtuple("Cache", ["value", "timeout"])

    def has_key(self, key: str):
        """Check if given `key` is in cache."""
        return key in self.__cache

    def get(self, key: str):
        """
        Get `key` from cache.

        Raises:
            KeyError: not found in the cache
        """
        if self.__cache[key].timeout > 0:
            self.get_timeout(key)
        return self.__cache[key].value

    def put(self, key: str, value: Any, timeout: int = 0):
        """Put `key` of `value` in the cache."""
        if timeout != 0:
            timeout = monotonic() + timeout
        self.__cache[key] = self.kv_tuple(value=value, timeout=timeout)

    def pop(self, key: str):
        """Removes and returns `key` from cache."""
        try:
            self.__cache.pop(key, None).value
        except AttributeError:
            pass

    def get_timeout(self, key: str):
        """Check if 'key' has expired"""
        now = monotonic()
        value, timeout = self.__cache[key]
        if now >= timeout:
            # Bust the cache
            del self.__cache[key]
            raise KeyError(f"{key} has expired")

    def get_or_put(self, key: str, timeout: int, method: Callable):
        try:
            return self.get(key)
        except KeyError:
            value = method()
            self.put(key, value, timeout)
            return value
