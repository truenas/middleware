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


class ZpoolNotFoundException(Exception):
    def __init__(self, pool: str):
        self.message = f"{pool!r} not found"
        super().__init__(self.message)


class ZpoolPoolUnhealthyException(Exception):
    def __init__(self, pool: str, health: str):
        self.message = f"{pool!r}: pool is {health}"
        super().__init__(self.message)


class ZpoolScanInvalidAction(Exception):
    def __init__(self, action: str):
        self.message = f"{action!r} is not a valid scan action (expected: start, pause, cancel)"
        super().__init__(self.message)


class ZpoolScanInvalidType(Exception):
    def __init__(self, scan_type: str):
        self.message = f"{scan_type!r} is not a valid scan type (expected: scrub, errorscrub)"
        super().__init__(self.message)


class ZpoolScrubAlreadyRunningException(Exception):
    def __init__(self, pool: str):
        self.message = f"{pool!r}: scrub already in progress"
        super().__init__(self.message)


class ZpoolScrubPausedException(Exception):
    def __init__(self, pool: str):
        self.message = f"{pool!r}: scrub is paused"
        super().__init__(self.message)


class ZpoolScrubPausedToCancelException(Exception):
    def __init__(self, pool: str):
        self.message = f"{pool!r}: scrub is paused and must be canceled before starting error scrub"
        super().__init__(self.message)


class ZpoolErrorScrubAlreadyRunningException(Exception):
    def __init__(self, pool: str):
        self.message = f"{pool!r}: error scrub already in progress"
        super().__init__(self.message)


class ZpoolErrorScrubPausedException(Exception):
    def __init__(self, pool: str):
        self.message = f"{pool!r}: error scrub is paused"
        super().__init__(self.message)


class ZpoolResiliverInProgressException(Exception):
    def __init__(self, pool: str):
        self.message = f"{pool!r}: resilver in progress"
        super().__init__(self.message)
