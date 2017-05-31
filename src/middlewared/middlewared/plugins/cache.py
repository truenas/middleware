from middlewared.schema import Any, Str, accepts
from middlewared.service import Service


class CacheService(Service):

    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super(CacheService, self).__init__(*args, **kwargs)
        self.__cache = {}

    @accepts(Str('key'))
    def has_key(self, key):
        """
        Check if given `key` is in cache.
        """
        return key in self.__cache

    @accepts(Str('key'))
    def get(self, key):
        """
        Get `key` from cache.

        Raises:
            KeyError: not found in the cache
        """
        return self.__cache[key]

    @accepts(Str('key'), Any('value'))
    def put(self, key, value):
        """
        Put `key` of `value` in the cache.
        """
        self.__cache[key] = value

    @accepts(Str('key'))
    def pop(self, key):
        """
        Removes and returns `key` from cache.
        """
        return self.__cache.pop(key, None)
