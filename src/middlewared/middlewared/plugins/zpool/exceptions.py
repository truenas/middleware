import errno

__all__ = (
    "ZpoolNotFoundException",
    "ZpoolPoolUnhealthyException",
    "ZpoolScanInvalidAction",
    "ZpoolScanInvalidType",
    "ZpoolScrubAlreadyRunningException",
    "ZpoolScrubPausedException",
    "ZpoolScrubPausedToCancelException",
    "ZpoolErrorScrubAlreadyRunningException",
    "ZpoolErrorScrubPausedException",
    "ZpoolResiliverInProgressException",
)


class ZpoolException(Exception):
    errno = errno.EFAULT

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ZpoolNotFoundException(ZpoolException):
    errno = errno.ENOENT

    def __init__(self, pool: str):
        super().__init__(f"{pool!r} not found")


class ZpoolPoolUnhealthyException(ZpoolException):
    errno = errno.EINVAL

    def __init__(self, pool: str, health: str):
        super().__init__(f"{pool!r}: pool is {health}")


class ZpoolScanInvalidAction(ZpoolException):
    errno = errno.EINVAL

    def __init__(self, action: str):
        super().__init__(f"{action!r} is not a valid scan action (expected: start, pause, cancel)")


class ZpoolScanInvalidType(ZpoolException):
    errno = errno.EINVAL

    def __init__(self, scan_type: str):
        super().__init__(f"{scan_type!r} is not a valid scan type (expected: scrub, errorscrub)")


class ZpoolScrubAlreadyRunningException(ZpoolException):
    errno = errno.EBUSY

    def __init__(self, pool: str):
        super().__init__(f"{pool!r}: scrub already in progress")


class ZpoolScrubPausedException(ZpoolException):
    errno = errno.EBUSY

    def __init__(self, pool: str):
        super().__init__(f"{pool!r}: scrub is paused")


class ZpoolScrubPausedToCancelException(ZpoolException):
    errno = errno.EBUSY

    def __init__(self, pool: str):
        super().__init__(f"{pool!r}: scrub is paused and must be canceled before starting error scrub")


class ZpoolErrorScrubAlreadyRunningException(ZpoolException):
    errno = errno.EBUSY

    def __init__(self, pool: str):
        super().__init__(f"{pool!r}: error scrub already in progress")


class ZpoolErrorScrubPausedException(ZpoolException):
    errno = errno.EBUSY

    def __init__(self, pool: str):
        super().__init__(f"{pool!r}: error scrub is paused")


class ZpoolResiliverInProgressException(ZpoolException):
    errno = errno.EBUSY

    def __init__(self, pool: str):
        super().__init__(f"{pool!r}: resilver in progress")
