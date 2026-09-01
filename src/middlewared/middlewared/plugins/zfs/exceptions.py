import dataclasses
import enum
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
    "ZFSRollbackBlocker",
    "ZFSRollbackBlockerReason",
    "ZFSRollbackConflictException",
    "ZFSRollbackFailedException",
)


def rollback_completed_note(completed: Sequence[str]) -> str:
    """Describe the datasets a partially-completed recursive rollback already rolled back."""
    if not completed:
        return ""
    return (
        "\nThe rollback already completed for the following datasets, so the tree is now "
        "partially rolled back:\n" + "\n".join(f"  {dataset}" for dataset in completed)
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


class ZFSRollbackBlockerReason(enum.StrEnum):
    CLONES = "CLONES"
    CLONE_DESTROY_FAILED = "CLONE_DESTROY_FAILED"
    HOLDS = "HOLDS"
    IN_USE = "IN_USE"
    UNDESTROYABLE_CLONE = "UNDESTROYABLE_CLONE"


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class ZFSRollbackBlocker:
    """A single reason why a snapshot newer than a rollback target cannot be destroyed."""

    snapshot: str
    """Path of the newer snapshot that stands in the way of the rollback."""
    reason: ZFSRollbackBlockerReason
    """What is blocking the destruction of `snapshot`."""
    names: tuple[str, ...]
    """Clone names, hold tags, or clone descendant names, depending on `reason`."""
    clone: str | None = None
    """The clone that cannot be destroyed. Only set for UNDESTROYABLE_CLONE."""
    truncated: bool = False
    """Whether `names` was cut short while being collected, so the list is incomplete."""

    def describe(self) -> str:
        names = ", ".join(self.names)
        if self.truncated:
            names += ", and more"

        if self.reason is ZFSRollbackBlockerReason.CLONES:
            if not names:
                return f"{self.snapshot!r} has dependent clones. Pass `recursive_clones: true` to destroy them."
            return (
                f"{self.snapshot!r} has dependent clones: {names}. "
                "Pass `recursive_clones: true` to destroy them."
            )
        elif self.reason is ZFSRollbackBlockerReason.CLONE_DESTROY_FAILED:
            if not names:
                return f"{self.snapshot!r} still has dependent clones that could not be destroyed."
            return f"{self.snapshot!r} still has dependent clones that could not be destroyed: {names}."
        elif self.reason is ZFSRollbackBlockerReason.HOLDS:
            return f"{self.snapshot!r} has holds: {names}. Release the holds before rolling back."
        elif self.reason is ZFSRollbackBlockerReason.IN_USE:
            return (
                f"{self.snapshot!r} is in use and cannot be destroyed. An in-flight `zfs send` or a "
                "`.zfs/snapshot` automount can hold a snapshot open; clear it and try again."
            )
        else:
            return (
                f"{self.snapshot!r} has the clone {self.clone!r}, which cannot be destroyed because it has "
                f"descendants of its own: {names}. Destroy them first."
            )


class ZFSRollbackBlockedException(Exception):
    def __init__(self, path: str, blockers: Sequence[ZFSRollbackBlocker], *, completed: Sequence[str] = ()):
        self.path = path
        self.blockers = tuple(blockers)
        self.completed = tuple(completed)
        details = "\n".join(f"  {blocker.describe()}" for blocker in self.blockers)
        self.message = (
            f"Cannot rollback to {path!r}: the following snapshots must be destroyed first, but are "
            f"blocked:\n{details}" + rollback_completed_note(self.completed)
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
            "Cannot rollback: more recent snapshots or bookmarks exist. Please pass `recursive: true` to "
            "delete the following snapshots and bookmarks recursively:\n" +
            "\n".join(f"  {conflict}" for conflict in self.conflicts)
        )
        super().__init__(path, self.conflicts)

    def __str__(self) -> str:
        return self.message


class ZFSRollbackFailedException(Exception):
    """A rollback, or a destroy the rollback depends on, failed for an operational reason."""

    def __init__(self, message: str, errnum: int, *, completed: Sequence[str] = ()):
        self.errnum = errnum
        self.completed = tuple(completed)
        self.message = message + rollback_completed_note(self.completed)
        super().__init__(self.message, errnum)

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
