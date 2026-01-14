from typing import Collection

__all__ = (
    "ZFSPathAlreadyExistsException",
    "ZFSPathInvalidException",
    "ZFSPathNotASnapshotException",
    "ZFSPathNotFoundException",
    "ZFSPathNotProvidedException",
)


class ZFSPathAlreadyExistsException(Exception):
    def __init__(self, path: str):
        self.message = f"{path!r} already exists"
        super().__init__(self.message)


class ZFSPathHasClonesException(Exception):
    def __init__(self, path: str, clones: Collection[str]):
        self.path = path
        self.clones = clones
        self.message = f"{path!r} has the following clones: {','.join(clones)}"
        super().__init__(self.message)


class ZFSPathHasHoldsException(Exception):
    def __init__(self, path: str, holds: Collection[str]):
        self.message = f"{path!r} has the following holds: {','.join(holds)}"
        super().__init__(self.message)


class ZFSPathInvalidException(Exception):
    pass


class ZFSPathNotASnapshotException(Exception):
    def __init__(self, path: str):
        self.message = f"{path!r} must be a snapshot path (containing '@')"
        super().__init__(self.message)


class ZFSPathNotFoundException(Exception):
    def __init__(self, path: str):
        self.message = f"{path!r} not found"
        super().__init__(self.message)


class ZFSPathNotProvidedException(Exception):
    pass
