class ConfigurationInvalidException(Exception):
    pass

class ChecksumFailException(Exception):
    pass

class ManifestInvalidException(Exception):
    pass

class ManifestInvalidSignature(Exception):
    pass

class UpdateException(Exception):
    pass

class UpdateIncompleteCacheException(UpdateException):
    pass

class UpdateInvalidCacheException(UpdateException):
    pass

class UpdateBusyCacheException(UpdateException):
    pass

class UpdateManifestNotFound(UpdateException):
    pass

class UpdateApplyException(UpdateException):
    pass

class UpdateBootEnvironmentException(UpdateException):
    pass

class UpdateSnapshotException(UpdateException):
    pass

class UpdatePackageException(UpdateException):
    pass
