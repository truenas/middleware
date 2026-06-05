from abc import ABC
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BeforeValidator, Field, StringConstraints
from zettarepl.snapshot.name import validate_snapshot_naming_schema

from middlewared.api.base import (
    BaseModel, JsonSchemaExtra, single_argument_args, NonEmptyString, NotRequired, Excluded, excluded_field
)
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
UserPropertyKey = Annotated[
    str,
    StringConstraints(pattern='.*:.*'),
    JsonSchemaExtra(description="ZFS user property key in namespace:property format (e.g., "
                                "'custom:backup_policy', 'org:created_by')."),
]


class PoolSnapshotEntryPropertyFields(BaseModel):
    value: str = Field(description="Current effective value of the ZFS property as a string.")
    rawvalue: str = Field(description="Raw string value of the ZFS property as stored.")
    source: Literal["NONE", "DEFAULT", "LOCAL", "TEMPORARY", "INHERITED", "RECEIVED"] = Field(
        description=(
            "Source of the property value.\n"
            "\n"
            "* `NONE`: Property is not set\n"
            "* `DEFAULT`: Using ZFS default value\n"
            "* `LOCAL`: Set locally on this snapshot\n"
            "* `TEMPORARY`: Temporary override value\n"
            "* `INHERITED`: Inherited from parent dataset\n"
            "* `RECEIVED`: Set by ZFS receive operation"
        ),
    )
    parsed: Any = Field(description="Property value parsed into the appropriate type (string, boolean, integer, etc.).")


class PoolSnapshotHoldTag(BaseModel):
    truenas: int = Field(default=NotRequired, description="Present if a hold has been placed on the snapshot.")


class PoolSnapshotRetentionPST(BaseModel):
    datetime_: datetime = Field(
        alias="datetime",
        description="Timestamp when the snapshot will be eligible for removal.",
    )
    source: Literal["periodic_snapshot_task"] = Field(
        description="Indicates retention is managed by a periodic snapshot task.",
    )
    periodic_snapshot_task_id: int = Field(description="ID of the periodic snapshot task managing this retention.")


class PoolSnapshotRetentionProperty(BaseModel):
    datetime_: datetime = Field(
        alias="datetime",
        description="Timestamp when the snapshot will be eligible for removal.",
    )
    source: Literal["property"] = Field(description="Indicates retention is managed by ZFS properties.")


class PoolSnapshotEntry(BaseModel):
    id: str = Field(description="Full snapshot identifier including dataset and snapshot name.")
    properties: dict[str, PoolSnapshotEntryPropertyFields] = Field(
        description="Object mapping ZFS property names to their values and metadata.",
    )
    pool: str = Field(description="Name of the ZFS pool containing this snapshot.")
    name: str = Field(description="Full name of the snapshot including dataset path.")
    type: Literal["SNAPSHOT"] = Field(description="Type identifier indicating this is a ZFS snapshot.")
    snapshot_name: str = Field(description="Just the snapshot name portion without the dataset path.")
    dataset: str = Field(description="Name of the dataset this snapshot was taken from.")
    createtxg: str = Field(description="Transaction group ID when the snapshot was created.")
    holds: PoolSnapshotHoldTag = Field(default=NotRequired, description="Returned when options.extra.holds is set.")
    retention: Annotated[
        PoolSnapshotRetentionPST | PoolSnapshotRetentionProperty,
        Field(discriminator="source")
    ] | None = Field(default=NotRequired, description="Returned when options.extra.retention is set.")


class PoolSnapshotCreateUpdateEntry(PoolSnapshotEntry):
    holds: Excluded = excluded_field()
    retention: Excluded = excluded_field()


class PoolSnapshotCreateTemplate(BaseModel, ABC):
    dataset: NonEmptyString = Field(description="Name of the dataset to create a snapshot of.")
    recursive: bool = Field(default=False, description="Whether to recursively snapshot child datasets.")
    exclude: list[str] = Field(default=[], description="Array of dataset patterns to exclude from recursive snapshots.")
    vmware_sync: bool = Field(default=False, description="Whether to sync VMware VMs before taking the snapshot.")
    properties: dict = Field(
        default={},
        description="Object mapping ZFS property names to values to set on the snapshot.",
    )


class PoolSnapshotCreateWithName(PoolSnapshotCreateTemplate):
    name: NonEmptyString = Field(description="Explicit name for the snapshot.")


class PoolSnapshotCreateWithSchema(PoolSnapshotCreateTemplate):
    naming_schema: ReplicationSnapshotNamingSchema = Field(
        description="Naming schema pattern to generate the snapshot name automatically.",
    )


class PoolSnapshotDeleteOptions(BaseModel):
    defer: bool = Field(default=False, description="Defer deletion of the snapshot.")
    recursive: bool = Field(default=False, description="Whether to recursively delete child snapshots.")


class PoolSnapshotHoldOptions(BaseModel):
    recursive: bool = Field(default=False, description="Hold snapshots recursively.")


class PoolSnapshotReleaseOptions(BaseModel):
    recursive: bool = Field(
        default=False,
        description=(
            "Whether to recursively release holds on child snapshots. Only the tags that are present on the parent "
            "snapshot will be removed."
        ),
    )


class PoolSnapshotRollbackOptions(BaseModel):
    recursive: bool = Field(
        default=False,
        description="Destroy any snapshots and bookmarks more recent than the one specified.",
    )
    recursive_clones: bool = Field(default=False, description="Just like `recursive`, but also destroy any clones.")
    force: bool = Field(default=False, description="Force unmount of any clones.")
    recursive_rollback: bool = Field(
        default=False,
        description=(
            "Do a complete recursive rollback of each child snapshot for `id`. If any child does not have specified "
            "snapshot, this operation will fail."
        ),
    )


class PoolSnapshotUserPropertyUpdate(BaseModel):
    key: UserPropertyKey = Field(description="The property name in namespace:property format.")
    value: str = Field(description="The new value to assign to the user property.")


class PoolSnapshotUpdate(BaseModel):
    user_properties_update: list[PoolSnapshotUserPropertyUpdate] = Field(
        default=[],
        description="Properties to update.",
    )
    user_properties_remove: list[UserPropertyKey] = Field(default=[], description="Properties to remove.")


@single_argument_args("data")
class PoolSnapshotCloneArgs(BaseModel):
    snapshot: NonEmptyString = Field(description="Full name of the snapshot to clone from.")
    dataset_dst: NonEmptyString = Field(description="Name for the new dataset created from the snapshot.")
    dataset_properties: dict = Field(
        default={},
        description="Object mapping ZFS property names to values to set on the cloned dataset.",
    )


class PoolSnapshotCloneResult(BaseModel):
    result: Literal[True] = Field(description="Clone succeeded.")


class PoolSnapshotCreateArgs(BaseModel):
    data: PoolSnapshotCreateWithName | PoolSnapshotCreateWithSchema = Field(
        description="Configuration for creating a snapshot with either an explicit name or naming schema.",
    )


class PoolSnapshotCreateResult(BaseModel):
    result: PoolSnapshotCreateUpdateEntry = Field(description="Information about the newly created snapshot.")


class PoolSnapshotDeleteArgs(BaseModel):
    id: str = Field(description="ID of the snapshot to delete.")
    options: PoolSnapshotDeleteOptions = Field(
        default_factory=PoolSnapshotDeleteOptions,
        description="Options for controlling snapshot deletion behavior.",
    )


class PoolSnapshotDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Indicates successful snapshot deletion.")


class PoolSnapshotHoldArgs(BaseModel):
    id: str = Field(description="ID of the snapshot to hold.")
    options: PoolSnapshotHoldOptions = Field(
        default_factory=PoolSnapshotHoldOptions,
        description="Options for controlling snapshot hold behavior.",
    )


class PoolSnapshotHoldResult(BaseModel):
    result: None = Field(description="Returns `null` on successful snapshot hold.")


class PoolSnapshotReleaseArgs(BaseModel):
    id: str = Field(description="ID of the held snapshot to release.")
    options: PoolSnapshotReleaseOptions = Field(
        default_factory=PoolSnapshotReleaseOptions,
        description="Options for controlling snapshot release behavior.",
    )


class PoolSnapshotReleaseResult(BaseModel):
    result: None = Field(description="Returns `null` on successful snapshot release.")


class PoolSnapshotRollbackArgs(BaseModel):
    id: str = Field(description="ID of the snapshot to rollback to.")
    options: PoolSnapshotRollbackOptions = Field(
        default_factory=PoolSnapshotRollbackOptions,
        description="Options for controlling snapshot rollback behavior.",
    )


class PoolSnapshotRollbackResult(BaseModel):
    result: None = Field(description="Returns `null` on successful snapshot rollback.")


class PoolSnapshotUpdateArgs(BaseModel):
    id: str = Field(description="ID of the snapshot to update.")
    data: PoolSnapshotUpdate = Field(description="The property updates to apply to the snapshot.")


class PoolSnapshotUpdateResult(BaseModel):
    result: PoolSnapshotCreateUpdateEntry = Field(description="Information about the updated snapshot.")


class PoolSnapshotRenameOptions(BaseModel):
    new_name: SNAPSHOT_NAME = Field(description="The new name for the snapshot.")
    force: bool = Field(
        default=False,
        description=(
            "This operation does not check whether the dataset is currently in use. Renaming an active dataset may "
            "disrupt SMB shares, iSCSI targets, snapshots, replication, and other services.\n"
            "\n"
            "Set Force only if you understand and accept the risks."
        ),
    )


class PoolSnapshotRenameArgs(BaseModel):
    id: NonEmptyString = Field(description="Current ID of the snapshot to rename.")
    options: PoolSnapshotRenameOptions = Field(
        description="The rename operation options including the new name and force flag.",
    )


class PoolSnapshotRenameResult(BaseModel):
    result: None = Field(description="Returns `null` on successful snapshot rename.")
