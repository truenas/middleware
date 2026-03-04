from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    single_argument_args,
)

__all__ = [
    "ReplicationConfigEntry", "ReplicationConfigUpdateArgs", "ReplicationConfigUpdateResult",
]


class ReplicationConfigEntry(BaseModel):
    id: int
    """Unique identifier for the replication configuration."""
    max_parallel_replication_tasks: int | None = Field(ge=1)
    """A maximum number of parallel replication tasks running."""


@single_argument_args("replication_config_update")
class ReplicationConfigUpdateArgs(ReplicationConfigEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class ReplicationConfigUpdateResult(BaseModel):
    result: ReplicationConfigEntry
    """The updated replication configuration."""
