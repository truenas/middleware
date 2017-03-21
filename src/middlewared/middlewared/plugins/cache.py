from middlewared.service import Service


class CacheService(Service):

    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super(CacheService, self).__init__(*args, **kwargs)
        self.__cache = {}

    def get(self, key):
        return self.__cache[key]

    def put(self, key, value):
        self.__cache[key] = value

    def pop(self, key):
        return self.__cache.pop(key, None)
