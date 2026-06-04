from pydantic import Field

from middlewared.api.base import (
    BaseModel,
)
from .replication import ReplicationEntry

__all__ = [
    "ReplicationRestoreArgs", "ReplicationRestoreResult",
]


class ReplicationRestoreOptions(BaseModel):
    name: str = Field(description="Name for the restored replication task.")
    target_dataset: str = Field(description="Dataset path where the replication should be restored to.")


class ReplicationRestoreArgs(BaseModel):
    id: int = Field(description="ID of the replication task to restore.")
    replication_restore: ReplicationRestoreOptions = Field(
        description="Configuration options for restoring the replication task.",
    )


class ReplicationRestoreResult(BaseModel):
    result: ReplicationEntry = Field(description="The restored replication task configuration.")
