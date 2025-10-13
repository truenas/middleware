__all__ = (
    "ZFSPathNotASnapshotException",
    "ZFSPathAlreadyExistsException",
    "ZFSPathNotFoundException",
    "ZFSPathNotProvidedException",
)


class ZFSPathNotASnapshotException(Exception):
    pass


class ZFSPathNotFoundException(Exception):
    def __init__(self, path):
        self.message = f"{path!r} not found"
        super().__init__(self.message)


class ZFSPathNotProvidedException(Exception):
    pass


class ZFSPathAlreadyExistsException(Exception):
    def __init__(self, path):
        self.message = f"{path!r} already exists"
        super().__init__(self.message)
