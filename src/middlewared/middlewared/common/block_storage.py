import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING

from middlewared.plugins.zfs.zvol_utils import zvol_path_to_name

if TYPE_CHECKING:
    from middlewared.main import Middleware

BlockStorageKind = Literal["ZVOL", "FILE"]


@dataclass(slots=True, frozen=True, kw_only=True)
class BlockStorageUse:
    """One zvol or file that a consumer has configured as a disk. `path` is spelled the way the consumer stores it."""

    kind: BlockStorageKind
    path: str
    id: int
    description: str
    data: dict[str, Any]


@dataclass(slots=True, frozen=True, kw_only=True)
class BlockStorageAttachment(BlockStorageUse):
    """A `BlockStorageUse` as the registry reports it: which delegate owns it and the canonical key it occupies."""

    namespace: str
    key: tuple[str, str]

    @property
    def method(self) -> str:
        return f"{self.namespace}.query"


def canonical_key(kind: BlockStorageKind, path: str) -> tuple[str, str]:
    if kind == "ZVOL":
        if not path.startswith("/dev/"):
            path = f"/dev/{path}"
        return "ZVOL", zvol_path_to_name(path)

    if os.path.exists(path):
        return "FILE", os.path.realpath(path)

    return "FILE", path


class BlockStorageDelegate(ABC):
    def __init__(self, middleware: "Middleware") -> None:
        self.middleware = middleware
        self.logger = middleware.logger

    @property
    @abstractmethod
    def namespace(self) -> str: ...

    @abstractmethod
    async def get_in_use(self) -> list[BlockStorageUse]: ...
