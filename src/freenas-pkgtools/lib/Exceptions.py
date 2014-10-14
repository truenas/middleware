class ConfigurationInvalidException(Exception):
    pass

class ChecksumFailException(Exception):
    pass

class ManifestInvalidException(Exception):
    pass

class UpdateIncompleteCacheException(Exception):
    pass

class UpdateInvalidCacheException(Exception):
    pass

class UpdateBusyCacheException(Exception):
    pass
