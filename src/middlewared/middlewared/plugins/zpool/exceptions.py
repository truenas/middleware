import errno

__all__ = (
    "ZpoolException",
    "ZpoolNotFoundException",
    "ZpoolNotMasterNodeException",
    "ZpoolPoolUnhealthyException",
    "ZpoolScanInvalidActionException",
    "ZpoolScanInvalidTypeException",
    "ZpoolScrubAlreadyRunningException",
    "ZpoolScrubPausedException",
    "ZpoolScrubPausedToCancelException",
    "ZpoolErrorScrubAlreadyRunningException",
    "ZpoolErrorScrubPausedException",
    "ZpoolScrubNotDueException",
    "ZpoolResiliverInProgressException",
    "ZpoolTooManyScrubsException",
)


class ZpoolException(Exception):
    errno = errno.EFAULT


class ZpoolNotFoundException(ZpoolException):
    errno = errno.ENOENT

    def __init__(self, pool: str):
        self.message = f"{pool!r} not found"
        super().__init__(pool)

    def __str__(self):
        return self.message


class ZpoolPoolUnhealthyException(ZpoolException):
    errno = errno.ENXIO

    def __init__(self, pool: str, health: str):
        self.message = f"{pool!r}: pool is {health}"
        super().__init__(pool, health)

    def __str__(self):
        return self.message


class ZpoolScanInvalidActionException(ZpoolException):
    errno = errno.EINVAL

    def __init__(self, action: str):
        self.message = f"{action!r} is not a valid scan action (expected: start, pause, cancel)"
        super().__init__(action)

    def __str__(self):
        return self.message


class ZpoolScanInvalidTypeException(ZpoolException):
    errno = errno.EINVAL

    def __init__(self, scan_type: str):
        self.message = f"{scan_type!r} is not a valid scan type (expected: scrub, errorscrub)"
        super().__init__(scan_type)

    def __str__(self):
        return self.message


class ZpoolScrubAlreadyRunningException(ZpoolException):
    errno = errno.EBUSY

    def __init__(self, pool: str):
        self.message = f"{pool!r}: scrub already in progress"
        super().__init__(pool)

    def __str__(self):
        return self.message


class ZpoolScrubPausedException(ZpoolException):
    errno = errno.EBUSY

    def __init__(self, pool: str):
        self.message = f"{pool!r}: scrub is paused"
        super().__init__(pool)

    def __str__(self):
        return self.message


class ZpoolScrubPausedToCancelException(ZpoolException):
    errno = errno.EBUSY

    def __init__(self, pool: str):
        self.message = f"{pool!r}: scrub is paused and must be canceled before starting error scrub"
        super().__init__(pool)

    def __str__(self):
        return self.message


class ZpoolErrorScrubAlreadyRunningException(ZpoolException):
    errno = errno.EBUSY

    def __init__(self, pool: str):
        self.message = f"{pool!r}: error scrub already in progress"
        super().__init__(pool)

    def __str__(self):
        return self.message


class ZpoolErrorScrubPausedException(ZpoolException):
    errno = errno.EBUSY

    def __init__(self, pool: str):
        self.message = f"{pool!r}: error scrub is paused"
        super().__init__(pool)

    def __str__(self):
        return self.message


class ZpoolNotMasterNodeException(ZpoolException):
    errno = errno.ENXIO

    def __init__(self, pool: str):
        self.message = f"{pool!r}: scrub skipped because this node is not the active controller"
        super().__init__(pool)

    def __str__(self):
        return self.message


class ZpoolScrubNotDueException(ZpoolException):
    errno = errno.EALREADY

    def __init__(self, pool: str):
        self.message = f"{pool!r}: scrub not due yet"
        super().__init__(pool)

    def __str__(self):
        return self.message


class ZpoolResiliverInProgressException(ZpoolException):
    errno = errno.EBUSY

    def __init__(self, pool: str):
        self.message = f"{pool!r}: resilver in progress"
        super().__init__(pool)

    def __str__(self):
        return self.message


class ZpoolTooManyScrubsException(ZpoolException):
    errno = errno.EBUSY

    def __init__(self, running: int):
        self.message = (
            f"{running} scrubs are already running. Running too many scrubs simultaneously "
            "will result in an unresponsive system. Refusing to start scrub."
        )
        super().__init__(running)

    def __str__(self):
        return self.message
