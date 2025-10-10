__all__ = (
    "ZFSPathNotFoundException",
    "ZFSPathNotProvidedException",
    "ZFSRenamePathAlreadyExistsException",
    "ZFSRenameNotASnapshotException",
    "ZFSRenamePathNotProvidedException",
)


class ZFSPathNotFoundException(Exception):
    def __init__(self, path):
        self.message = f"{path!r} not found"
        super().__init__(self.message)


class ZFSPathNotProvidedException(Exception):
    pass


class ZFSRenamePathAlreadyExistsException(Exception):
    def __init__(self, path):
        self.message = f"{path!r} already exists"
        super().__init__(self.message)


class ZFSRenameNotASnapshotException(Exception):
    pass


class ZFSRenamePathNotProvidedException(Exception):
    pass
