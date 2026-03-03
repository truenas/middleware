from typing import Iterable

__all__ = (
    "ZFSKeyAlreadyLoadedException",
    "ZFSNotEncryptedException",
    "ZFSPathAlreadyExistsException",
    "ZFSPathInvalidException",
    "ZFSPathNotASnapshotException",
    "ZFSPathNotFoundException",
    "ZFSPathNotProvidedException",
)


class ZFSKeyAlreadyLoadedException(Exception):
    def __init__(self, path: str):
        self.message = f"{path!r} key is already loaded"
        super().__init__(self.message)


class ZFSNotEncryptedException(Exception):
    def __init__(self, path: str):
        self.message = f"{path!r} is not encrypted"
        super().__init__(self.message)


class ZFSPathAlreadyExistsException(Exception):
    def __init__(self, path: str):
        self.message = f"{path!r} already exists"
        super().__init__(self.message)


class ZFSPathHasClonesException(Exception):
    def __init__(self, path: str, clones: Iterable[str]):
        self.path = path
        self.clones = clones
        self.message = f"{path!r} has the following clones: {','.join(clones)}"
        super().__init__(self.message)


class ZFSPathHasHoldsException(Exception):
    def __init__(self, path: str, holds: Iterable[str]):
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
