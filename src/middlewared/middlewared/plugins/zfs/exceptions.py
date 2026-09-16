from collections.abc import Sequence

__all__ = (
    "ZFSKeyAlreadyLoadedException",
    "ZFSNotEncryptedException",
    "ZFSPathAlreadyExistsException",
    "ZFSPathException",
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


class ZFSPathException(Exception):
    """Base for errors about one ZFS path. Subclasses set ``reason``, the predicate that follows the path."""

    reason = "is invalid"

    def __init__(self, path: str, reason: str | None = None):
        self.path = path
        self.message = f"{path!r} {reason or self.reason}"
        super().__init__(path)

    def __str__(self) -> str:
        return self.message


class ZFSKeyAlreadyLoadedException(ZFSPathException):
    reason = "key is already loaded"


class ZFSNotEncryptedException(ZFSPathException):
    reason = "is not encrypted"


class ZFSPathAlreadyExistsException(ZFSPathException):
    reason = "already exists"


class ZFSPathHasClonesException(ZFSPathException):
    def __init__(self, path: str, clones: Sequence[str]):
        self.clones = tuple(clones)
        super().__init__(path, f"has the following clones: {', '.join(self.clones)}")


class ZFSPathHasHoldsException(ZFSPathException):
    def __init__(self, path: str, holds: Sequence[str]):
        self.holds = tuple(holds)
        super().__init__(path, f"has the following holds: {', '.join(self.holds)}")


class ZFSPathInvalidException(ZFSPathException):
    """The path is unfit for the requested operation. Pass a ``reason`` saying why."""


class ZFSPathNotASnapshotException(ZFSPathException):
    reason = "must be a snapshot path (containing '@')"


class ZFSPathNotFoundException(ZFSPathException):
    reason = "not found"


class ZFSPathNotProvidedException(Exception):
    def __init__(self) -> None:
        self.message = "path not provided"
        super().__init__(self.message)


class ZFSRollbackBlockedException(Exception):
    """Snapshots newer than the rollback target have holds, or clones that may not be destroyed."""

    def __init__(self, path: str, blockers: Sequence[str]):
        self.path = path
        self.blockers = tuple(blockers)
        self.message = (
            f"Cannot rollback to {path!r}: the following snapshots must be destroyed first, but are blocked:\n"
            + "\n".join(f"  {blocker}" for blocker in self.blockers)
        )
        super().__init__(path, self.blockers)

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
