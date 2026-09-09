from typing import Iterable, Sequence

__all__ = (
    "ZFSKeyAlreadyLoadedException",
    "ZFSNotEncryptedException",
    "ZFSPathAlreadyExistsException",
    "ZFSPathHasClonesException",
    "ZFSPathHasHoldsException",
    "ZFSPathInvalidException",
    "ZFSPathNotASnapshotException",
    "ZFSPathNotFoundException",
    "ZFSPathNotProvidedException",
    "ZFSRollbackBlockedException",
    "ZFSRollbackConflictException",
    "ZFSRollbackFailedException",
)


class ZFSKeyAlreadyLoadedException(Exception):
    def __init__(self, path: str):
        self.message = f"{path!r} key is already loaded"
        super().__init__(path)

    def __str__(self) -> str:
        return self.message


class ZFSNotEncryptedException(Exception):
    def __init__(self, path: str):
        self.message = f"{path!r} is not encrypted"
        super().__init__(path)

    def __str__(self) -> str:
        return self.message


class ZFSPathAlreadyExistsException(Exception):
    def __init__(self, path: str):
        self.message = f"{path!r} already exists"
        super().__init__(path)

    def __str__(self) -> str:
        return self.message


class ZFSPathHasClonesException(Exception):
    def __init__(self, path: str, clones: Iterable[str]):
        self.path = path
        self.clones = clones
        self.message = f"{path!r} has the following clones: {','.join(clones)}"
        super().__init__(path, clones)

    def __str__(self) -> str:
        return self.message


class ZFSPathHasHoldsException(Exception):
    def __init__(self, path: str, holds: Iterable[str]):
        self.message = f"{path!r} has the following holds: {','.join(holds)}"
        super().__init__(path, holds)

    def __str__(self) -> str:
        return self.message


class ZFSRollbackBlockedException(Exception):
    """Snapshots newer than the rollback target have holds, or clones that may not be destroyed."""

    def __init__(self, path: str, blockers: Sequence[str]):
        self.path = path
        self.blockers = tuple(blockers)
        self.message = (
            f"Cannot rollback to {path!r}: the following snapshots must be destroyed first, but are blocked:\n"
            + "\n".join(f"  {blocker}" for blocker in self.blockers)
        )
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


class ZFSRollbackConflictException(Exception):
    """Snapshots newer than the rollback target exist and may not be destroyed."""

    def __init__(self, path: str, conflicts: Sequence[str]):
        self.path = path
        self.conflicts = tuple(conflicts)
        self.message = (
            "Cannot rollback: more recent snapshots exist. Please pass `recursive: true` to "
            "delete the following snapshots recursively:\n" +
            "\n".join(f"  {conflict}" for conflict in self.conflicts)
        )
        super().__init__(path, self.conflicts)

    def __str__(self) -> str:
        return self.message


class ZFSRollbackFailedException(Exception):
    """A rollback, or a destroy the rollback depends on, failed for an operational reason."""

    def __init__(self, message: str, errnum: int):
        self.errnum = errnum
        self.message = message
        super().__init__(message, errnum)

    def __str__(self) -> str:
        return self.message


class ZFSPathInvalidException(Exception):
    pass


class ZFSPathNotASnapshotException(Exception):
    def __init__(self, path: str):
        self.message = f"{path!r} must be a snapshot path (containing '@')"
        super().__init__(path)

    def __str__(self) -> str:
        return self.message


class ZFSPathNotFoundException(Exception):
    def __init__(self, path: str):
        self.message = f"{path!r} not found"
        super().__init__(path)

    def __str__(self) -> str:
        return self.message


class ZFSPathNotProvidedException(Exception):
    pass
