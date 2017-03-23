from middlewared.schema import Any, Str, accepts
from middlewared.service import Service


class CacheService(Service):

    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super(CacheService, self).__init__(*args, **kwargs)
        self.__cache = {}

    @accepts(Str('key'))
    def get(self, key):
        return self.__cache[key]

    @accepts(Str('key'), Any('value'))
    def put(self, key, value):
        self.__cache[key] = value

    @accepts(Str('key'))
    def pop(self, key):
        return self.__cache.pop(key, None)
