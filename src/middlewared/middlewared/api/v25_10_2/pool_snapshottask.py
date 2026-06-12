from typing import Any, Literal

from pydantic import Field

from middlewared.api.base import BaseModel, ForUpdateMetaclass, SnapshotNameSchema, TimeString

from .common import CronModel

__all__ = [
    "PoolSnapshotTaskDBEntry", "PeriodicSnapshotTaskEntry", "PeriodicSnapshotTaskCreateArgs",
    "PeriodicSnapshotTaskCreateResult", "PeriodicSnapshotTaskUpdateArgs", "PeriodicSnapshotTaskUpdateResult",
    "PeriodicSnapshotTaskDeleteArgs", "PeriodicSnapshotTaskDeleteResult", "PeriodicSnapshotTaskMaxCountArgs",
    "PeriodicSnapshotTaskMaxCountResult", "PeriodicSnapshotTaskMaxTotalCountArgs",
    "PeriodicSnapshotTaskMaxTotalCountResult", "PeriodicSnapshotTaskRunArgs", "PeriodicSnapshotTaskRunResult",
    "PeriodicSnapshotTaskUpdateWillChangeRetentionForArgs", "PeriodicSnapshotTaskUpdateWillChangeRetentionForResult",
    "PeriodicSnapshotTaskDeleteWillChangeRetentionForArgs", "PeriodicSnapshotTaskDeleteWillChangeRetentionForResult",
]


class PoolSnapshotTaskCron(CronModel):
    minute: str = Field(default="00", description="Minute when snapshots should be taken (cron format).")
    begin: TimeString = Field(default="00:00", description="Start time of the window when snapshots can be taken.")
    end: TimeString = Field(default="23:59", description="End time of the window when snapshots can be taken.")


class PoolSnapshotTaskCreate(BaseModel):
    dataset: str = Field(description="The dataset to take snapshots of.")
    recursive: bool = Field(default=False, description="Whether to recursively snapshot child datasets.")
    lifetime_value: int = Field(
        default=2,
        description="Number of time units to retain snapshots. `lifetime_unit` gives the time unit.",
    )
    lifetime_unit: Literal["HOUR", "DAY", "WEEK", "MONTH", "YEAR"] = Field(
        default="WEEK",
        description="Unit of time for snapshot retention.",
    )
    enabled: bool = Field(default=True, description="Whether this periodic snapshot task is enabled.")
    exclude: list[str] = Field(default=[], description="Array of dataset patterns to exclude from recursive snapshots.")
    naming_schema: SnapshotNameSchema = Field(
        default="auto-%Y-%m-%d_%H-%M",
        description="Naming pattern for generated snapshots using strftime format.",
    )
    allow_empty: bool = Field(default=True, description="Whether to take snapshots even if no data has changed.")
    schedule: PoolSnapshotTaskCron = Field(
        default_factory=PoolSnapshotTaskCron,
        description="Cron schedule for when snapshots should be taken.",
    )


class PoolSnapshotTaskUpdate(PoolSnapshotTaskCreate, metaclass=ForUpdateMetaclass):
    fixate_removal_date: bool = Field(
        description="Whether to fix the removal date of existing snapshots when retention settings change.",
    )


class PoolSnapshotTaskUpdateWillChangeRetentionFor(PoolSnapshotTaskCreate, metaclass=ForUpdateMetaclass):
    pass


class PoolSnapshotTaskDeleteOptions(BaseModel):
    fixate_removal_date: bool = Field(
        default=False,
        description="Whether to fix the removal date of existing snapshots when the task is deleted.",
    )


class PoolSnapshotTaskDBEntry(PoolSnapshotTaskCreate):
    id: int = Field(description="Unique identifier for the periodic snapshot task.")
    state: str = Field(description="Current state of the task.")


class PeriodicSnapshotTaskEntry(PoolSnapshotTaskDBEntry):
    vmware_sync: bool = Field(description="Whether VMware VMs are synced before taking snapshots.")
    state: Any = Field(description="Detailed state information for the task.")


class PeriodicSnapshotTaskCreateArgs(BaseModel):
    data: PoolSnapshotTaskCreate = Field(description="Configuration for the new periodic snapshot task.")


class PeriodicSnapshotTaskCreateResult(BaseModel):
    result: PeriodicSnapshotTaskEntry = Field(description="The newly created periodic snapshot task configuration.")


class PeriodicSnapshotTaskUpdateArgs(BaseModel):
    id: int = Field(description="ID of the periodic snapshot task to update.")
    data: PoolSnapshotTaskUpdate = Field(description="Updated configuration for the periodic snapshot task.")


class PeriodicSnapshotTaskUpdateResult(BaseModel):
    result: PeriodicSnapshotTaskEntry = Field(description="The updated periodic snapshot task configuration.")


class PeriodicSnapshotTaskDeleteArgs(BaseModel):
    id: int = Field(description="ID of the periodic snapshot task to delete.")
    options: PoolSnapshotTaskDeleteOptions = Field(
        default_factory=PoolSnapshotTaskDeleteOptions,
        description="Options for controlling task deletion behavior.",
    )


class PeriodicSnapshotTaskDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Indicates successful deletion of the periodic snapshot task.")


class PeriodicSnapshotTaskMaxCountArgs(BaseModel):
    pass


class PeriodicSnapshotTaskMaxCountResult(BaseModel):
    result: int = Field(description="Maximum number of periodic snapshot tasks allowed.")


class PeriodicSnapshotTaskMaxTotalCountArgs(BaseModel):
    pass


class PeriodicSnapshotTaskMaxTotalCountResult(BaseModel):
    result: int = Field(description="Maximum total number of snapshots allowed across all tasks.")


class PeriodicSnapshotTaskRunArgs(BaseModel):
    id: int = Field(description="ID of the periodic snapshot task to run immediately.")


class PeriodicSnapshotTaskRunResult(BaseModel):
    result: None = Field(description="Returns `null` on successful task execution.")


class PeriodicSnapshotTaskUpdateWillChangeRetentionForArgs(BaseModel):
    id: int = Field(description="ID of the periodic snapshot task to analyze.")
    data: PoolSnapshotTaskUpdateWillChangeRetentionFor = Field(description="Proposed configuration changes to analyze.")


class PeriodicSnapshotTaskUpdateWillChangeRetentionForResult(BaseModel):
    result: dict[str, list[str]] = Field(
        description="Object mapping retention change types to arrays of affected snapshot names.",
    )


class PeriodicSnapshotTaskDeleteWillChangeRetentionForArgs(BaseModel):
    id: int = Field(description="ID of the periodic snapshot task to analyze for deletion impact.")


class PeriodicSnapshotTaskDeleteWillChangeRetentionForResult(BaseModel):
    result: dict[str, list[str]] = Field(
        description=(
            "Object mapping retention change types to arrays of snapshots that would be affected by task deletion."
        ),
    )
