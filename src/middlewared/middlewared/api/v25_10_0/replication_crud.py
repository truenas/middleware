from middlewared.api.base import (
    BaseModel,
)
from .replication import ReplicationEntry

__all__ = [
    "ReplicationRestoreArgs", "ReplicationRestoreResult",
]


class ReplicationRestoreOptions(BaseModel):
    name: str
    """Name for the restored replication task."""
    target_dataset: str
    """Dataset path where the replication should be restored to."""


class ReplicationRestoreArgs(BaseModel):
    id: int
    """ID of the replication task to restore."""
    replication_restore: ReplicationRestoreOptions
    """Configuration options for restoring the replication task."""


class ReplicationRestoreResult(BaseModel):
    result: ReplicationEntry
    """The restored replication task configuration."""
