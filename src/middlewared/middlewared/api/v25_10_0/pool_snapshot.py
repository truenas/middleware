from abc import ABC
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field, AfterValidator
from zettarepl.snapshot.name import validate_snapshot_naming_schema

from middlewared.api.base import BaseModel, single_argument_args, NonEmptyString, NotRequired, Excluded, excluded_field
from middlewared.plugins.zfs_.validation_utils import validate_snapshot_name


__all__ = [
    "PoolSnapshotEntry", "PoolSnapshotCloneArgs", "PoolSnapshotCloneResult", "PoolSnapshotCreateArgs",
    "PoolSnapshotCreateResult", "PoolSnapshotDeleteArgs", "PoolSnapshotDeleteResult", "PoolSnapshotHoldArgs",
    "PoolSnapshotHoldResult", "PoolSnapshotReleaseArgs", "PoolSnapshotReleaseResult", "PoolSnapshotRollbackArgs",
    "PoolSnapshotRollbackResult", "PoolSnapshotUpdateArgs", "PoolSnapshotUpdateResult", "PoolSnapshotRenameArgs",
    "PoolSnapshotRenameResult",
]


def _validate_snapshot_name(v: str) -> str:
    if not validate_snapshot_name(v):
        raise ValueError('Please provide a valid snapshot name according to ZFS standards i.e <dataset>@<snapshot>')
    return v


def validate_snapshot_naming_schema_and_return(value: NonEmptyString):
    validate_snapshot_naming_schema(value)
    return value


ReplicationSnapshotNamingSchema = Annotated[NonEmptyString, AfterValidator(validate_snapshot_naming_schema_and_return)]
SNAPSHOT_NAME = Annotated[
    NonEmptyString,
    BeforeValidator(_validate_snapshot_name),
]
UserPropertyKey = Annotated[str, Field(pattern='.*:.*')]


class PoolSnapshotEntryPropertyFields(BaseModel):
    value: str
    """Current effective value of the ZFS property as a string."""
    rawvalue: str
    """Raw string value of the ZFS property as stored."""
    source: Literal["NONE", "DEFAULT", "LOCAL", "TEMPORARY", "INHERITED", "RECEIVED"]
    """Source of the property value.

    * `NONE`: Property is not set
    * `DEFAULT`: Using ZFS default value
    * `LOCAL`: Set locally on this snapshot
    * `TEMPORARY`: Temporary override value
    * `INHERITED`: Inherited from parent dataset
    * `RECEIVED`: Set by ZFS receive operation
    """
    parsed: Any
    """Property value parsed into the appropriate type (string, boolean, integer, etc.)."""


class PoolSnapshotHoldTag(BaseModel):
    truenas: int = NotRequired
    """Present if a hold has been placed on the snapshot."""


class PoolSnapshotRetentionPST(BaseModel):
    datetime_: datetime = Field(alias="datetime")
    """Timestamp when the snapshot will be eligible for removal."""
    source: Literal["periodic_snapshot_task"]
    """Indicates retention is managed by a periodic snapshot task."""
    periodic_snapshot_task_id: int
    """ID of the periodic snapshot task managing this retention."""


class PoolSnapshotRetentionProperty(BaseModel):
    datetime_: datetime = Field(alias="datetime")
    """Timestamp when the snapshot will be eligible for removal."""
    source: Literal["property"]
    """Indicates retention is managed by ZFS properties."""


class PoolSnapshotEntry(BaseModel):
    id: str
    """Full snapshot identifier including dataset and snapshot name."""
    properties: dict[str, PoolSnapshotEntryPropertyFields]
    """Object mapping ZFS property names to their values and metadata."""
    pool: str
    """Name of the ZFS pool containing this snapshot."""
    name: str
    """Full name of the snapshot including dataset path."""
    type: Literal["SNAPSHOT"]
    """Type identifier indicating this is a ZFS snapshot."""
    snapshot_name: str
    """Just the snapshot name portion without the dataset path."""
    dataset: str
    """Name of the dataset this snapshot was taken from."""
    createtxg: str
    """Transaction group ID when the snapshot was created."""
    holds: PoolSnapshotHoldTag = NotRequired
    """Returned when options.extra.holds is set."""
    retention: Annotated[
        PoolSnapshotRetentionPST | PoolSnapshotRetentionProperty,
        Field(discriminator="source")
    ] | None = NotRequired
    """Returned when options.extra.retention is set."""


class PoolSnapshotCreateUpdateEntry(PoolSnapshotEntry):
    holds: Excluded = excluded_field()
    retention: Excluded = excluded_field()


class PoolSnapshotCreateTemplate(BaseModel, ABC):
    dataset: NonEmptyString
    """Name of the dataset to create a snapshot of."""
    recursive: bool = False
    """Whether to recursively snapshot child datasets."""
    exclude: list[str] = []
    """Array of dataset patterns to exclude from recursive snapshots."""
    vmware_sync: bool = False
    """Whether to sync VMware VMs before taking the snapshot."""
    properties: dict = {}
    """Object mapping ZFS property names to values to set on the snapshot."""


class PoolSnapshotCreateWithName(PoolSnapshotCreateTemplate):
    name: NonEmptyString
    """Explicit name for the snapshot."""


class PoolSnapshotCreateWithSchema(PoolSnapshotCreateTemplate):
    naming_schema: ReplicationSnapshotNamingSchema
    """Naming schema pattern to generate the snapshot name automatically."""


class PoolSnapshotDeleteOptions(BaseModel):
    defer: bool = False
    """Defer deletion of the snapshot."""
    recursive: bool = False
    """Whether to recursively delete child snapshots."""


class PoolSnapshotHoldOptions(BaseModel):
    recursive: bool = False
    """Hold snapshots recursively."""


class PoolSnapshotReleaseOptions(BaseModel):
    recursive: bool = False
    """Whether to recursively release holds on child snapshots. Only the tags that are present on the parent snapshot \
    will be removed."""


class PoolSnapshotRollbackOptions(BaseModel):
    recursive: bool = False
    """Destroy any snapshots and bookmarks more recent than the one specified."""
    recursive_clones: bool = False
    """Just like `recursive`, but also destroy any clones."""
    force: bool = False
    """Force unmount of any clones."""
    recursive_rollback: bool = False
    """Do a complete recursive rollback of each child snapshot for `id`. If any child does not have specified \
    snapshot, this operation will fail."""


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
    result: PoolSnapshotCreateUpdateEntry


class PoolSnapshotDeleteArgs(BaseModel):
    id: str
    """ID of the snapshot to delete."""
    options: PoolSnapshotDeleteOptions = Field(default_factory=PoolSnapshotDeleteOptions)


class PoolSnapshotDeleteResult(BaseModel):
    result: Literal[True]


class PoolSnapshotHoldArgs(BaseModel):
    id: str
    """ID of the snapshot to hold."""
    options: PoolSnapshotHoldOptions = Field(default_factory=PoolSnapshotHoldOptions)


class PoolSnapshotHoldResult(BaseModel):
    result: None


class PoolSnapshotReleaseArgs(BaseModel):
    id: str
    """ID of the held snapshot to release."""
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
    result: PoolSnapshotCreateUpdateEntry


class PoolSnapshotRenameOptions(BaseModel):
    new_name: SNAPSHOT_NAME
    force: bool = False
    """
    This operation does not check whether the dataset is currently in use. Renaming an active dataset may disrupt \
    SMB shares, iSCSI targets, snapshots, replication, and other services.

    Set Force only if you understand and accept the risks.
    """


class PoolSnapshotRenameArgs(BaseModel):
    id: NonEmptyString
    options: PoolSnapshotRenameOptions


class PoolSnapshotRenameResult(BaseModel):
    result: None
