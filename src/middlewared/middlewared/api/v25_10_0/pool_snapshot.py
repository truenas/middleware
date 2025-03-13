from abc import ABC
from typing import Annotated, Any, Literal

from pydantic import Field, AfterValidator
from zettarepl.snapshot.name import validate_snapshot_naming_schema

from middlewared.api.base import BaseModel, single_argument_args, NonEmptyString


__all__ = [
    "PoolSnapshotEntry", "PoolSnapshotCloneArgs", "PoolSnapshotCloneResult", "PoolSnapshotCreateArgs",
    "PoolSnapshotCreateResult", "PoolSnapshotDeleteArgs", "PoolSnapshotDeleteResult", "PoolSnapshotHoldArgs",
    "PoolSnapshotHoldResult", "PoolSnapshotReleaseArgs", "PoolSnapshotReleaseResult", "PoolSnapshotRollbackArgs",
    "PoolSnapshotRollbackResult", "PoolSnapshotUpdateArgs", "PoolSnapshotUpdateResult",
]


def validate_snapshot_naming_schema_and_return(value: NonEmptyString):
    validate_snapshot_naming_schema(value)
    return value


ReplicationSnapshotNamingSchema = Annotated[NonEmptyString, AfterValidator(validate_snapshot_naming_schema_and_return)]
UserPropertyKey = Annotated[str, Field(pattern=r'.*:.*')]


class PoolSnapshotEntryPropertyFields(BaseModel):
    value: str
    rawvalue: str
    source: Literal["INHERITED", "NONE", "DEFAULT"]
    parsed: Any


class PoolSnapshotEntry(BaseModel):
    properties: dict[str, PoolSnapshotEntryPropertyFields]
    pool: str
    name: str
    type: Literal["SNAPSHOT"]
    snapshot_name: str
    dataset: str
    id: str
    createtxg: str


class PoolSnapshotCreateTemplate(BaseModel, ABC):
    dataset: NonEmptyString
    recursive: bool = False
    exclude: list[str] = []
    vmware_sync: bool = False
    properties: dict = {}


class PoolSnapshotCreateWithName(PoolSnapshotCreateTemplate):
    name: NonEmptyString


class PoolSnapshotCreateWithSchema(PoolSnapshotCreateTemplate):
    naming_schema: ReplicationSnapshotNamingSchema


class PoolSnapshotDeleteOptions(BaseModel):
    defer: bool = False
    """Defer deletion of the snapshot."""
    recursive: bool = False


class PoolSnapshotHoldOptions(BaseModel):
    recursive: bool = False
    """Hold snapshots recursively."""


class PoolSnapshotReleaseOptions(BaseModel):
    recursive: bool = False
    """Release snapshots recursively. Only the tags that are present on the parent snapshot will be removed."""


class PoolSnapshotRollbackOptions(BaseModel):
    recursive: bool = False
    """Destroy any snapshots and bookmarks more recent than the one specified."""
    recursive_clones: bool = False
    """Just like `recursive`, but also destroy any clones."""
    force: bool = False
    """Force unmount of any clones."""
    recursive_rollback: bool = False
    """Do a complete recursive rollback of each child snapshot for `id`. If any child does not have specified snapshot,
    this operation will fail."""


class PoolSnapshotUserPropertyUpdate(BaseModel):
    key: UserPropertyKey
    value: str


class PoolSnapshotUpdate(BaseModel):
    user_properties_update: list[PoolSnapshotUserPropertyUpdate] = []
    """Properties to update."""
    user_properties_remove: list[UserPropertyKey] = []
    """Properties to remove."""


@single_argument_args("data")
class PoolSnapshotCloneArgs(BaseModel):
    snapshot: NonEmptyString
    dataset_dst: NonEmptyString
    dataset_properties: dict = {}


class PoolSnapshotCloneResult(BaseModel):
    result: Literal[True]
    """Clone succeeded."""


class PoolSnapshotCreateArgs(BaseModel):
    data: PoolSnapshotCreateWithName | PoolSnapshotCreateWithSchema


class PoolSnapshotCreateResult(BaseModel):
    result: PoolSnapshotEntry


class PoolSnapshotDeleteArgs(BaseModel):
    id: str
    options: PoolSnapshotDeleteOptions = Field(default_factory=PoolSnapshotDeleteOptions)


class PoolSnapshotDeleteResult(BaseModel):
    result: Literal[True]


class PoolSnapshotHoldArgs(BaseModel):
    id: str
    options: PoolSnapshotHoldOptions = Field(default_factory=PoolSnapshotHoldOptions)


class PoolSnapshotHoldResult(BaseModel):
    result: None


class PoolSnapshotReleaseArgs(BaseModel):
    id: str
    options: PoolSnapshotReleaseOptions = Field(default_factory=PoolSnapshotReleaseOptions)


class PoolSnapshotReleaseResult(BaseModel):
    result: None


class PoolSnapshotRollbackArgs(BaseModel):
    id: str
    """ID of the snapshot to rollback to."""
    options: PoolSnapshotRollbackOptions = Field(default_factory=PoolSnapshotRollbackOptions)


class PoolSnapshotRollbackResult(BaseModel):
    result: None


class PoolSnapshotUpdateArgs(BaseModel):
    id: str
    data: PoolSnapshotUpdate


class PoolSnapshotUpdateResult(BaseModel):
    result: PoolSnapshotEntry
