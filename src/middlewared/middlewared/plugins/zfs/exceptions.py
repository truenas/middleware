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
    HOLDS = "HOLDS"
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
            return (
                f"{self.snapshot!r} has dependent clones: {names}. "
                "Pass `recursive_clones: true` to destroy them."
            )
        elif self.reason is ZFSRollbackBlockerReason.HOLDS:
            return f"{self.snapshot!r} has holds: {names}. Release the holds before rolling back."
        else:
            return (
                f"{self.snapshot!r} has the clone {self.clone!r}, which cannot be destroyed because it has "
                f"descendants of its own: {names}. Destroy them first."
            )


class ZFSRollbackBlockedException(Exception):
    def __init__(self, path: str, blockers: Sequence[ZFSRollbackBlocker]):
        self.path = path
        self.blockers = tuple(blockers)
        details = "\n".join(f"  {blocker.describe()}" for blocker in self.blockers)
        self.message = (
            f"Cannot rollback to {path!r}: the following snapshots must be destroyed first, but are "
            f"blocked:\n{details}"
        )
        super().__init__(path, self.blockers)

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
