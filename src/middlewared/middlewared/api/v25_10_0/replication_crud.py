from middlewared.api.base import (
    BaseModel,
)
from .replication import ReplicationEntry

__all__ = [
    "ReplicationRestoreArgs", "ReplicationRestoreResult",
]


class ReplicationRestoreOptions(BaseModel):
    name: str
    target_dataset: str


class ReplicationRestoreArgs(BaseModel):
    id: int
    replication_restore: ReplicationRestoreOptions


class ReplicationRestoreResult(BaseModel):
    result: ReplicationEntry
