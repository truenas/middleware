__all__ = (
    "ZFSPathAlreadyExistsException",
    "ZFSPathInvalidException",
    "ZFSPathNotASnapshotException",
    "ZFSPathNotFoundException",
    "ZFSPathNotProvidedException",
)


class ZFSPathAlreadyExistsException(Exception):
    def __init__(self, path):
        self.message = f"{path!r} already exists"
        super().__init__(self.message)


class ZFSPathInvalidException(Exception):
    pass


class ZFSPathNotASnapshotException(Exception):
    pass


class ZFSPathNotFoundException(Exception):
    def __init__(self, path):
        self.message = f"{path!r} not found"
        super().__init__(self.message)


class ZFSPathNotProvidedException(Exception):
    pass
