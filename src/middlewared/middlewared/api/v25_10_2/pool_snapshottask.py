from typing import Any, Literal

from pydantic import Field

from middlewared.api.base import BaseModel, ForUpdateMetaclass, TimeString, SnapshotNameSchema
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
    minute: str = "00"
    """Minute when snapshots should be taken (cron format)."""
    begin: TimeString = "00:00"
    """Start time of the window when snapshots can be taken."""
    end: TimeString = "23:59"
    """End time of the window when snapshots can be taken."""


class PoolSnapshotTaskCreate(BaseModel):
    dataset: str
    """The dataset to take snapshots of."""
    recursive: bool = False
    """Whether to recursively snapshot child datasets."""
    lifetime_value: int = 2
    """Number of time units to retain snapshots. `lifetime_unit` gives the time unit."""
    lifetime_unit: Literal["HOUR", "DAY", "WEEK", "MONTH", "YEAR"] = "WEEK"
    """Unit of time for snapshot retention."""
    enabled: bool = True
    """Whether this periodic snapshot task is enabled."""
    exclude: list[str] = []
    """Array of dataset patterns to exclude from recursive snapshots."""
    naming_schema: SnapshotNameSchema = "auto-%Y-%m-%d_%H-%M"
    """Naming pattern for generated snapshots using strftime format."""
    allow_empty: bool = True
    """Whether to take snapshots even if no data has changed."""
    schedule: PoolSnapshotTaskCron = Field(default_factory=PoolSnapshotTaskCron)
    """Cron schedule for when snapshots should be taken."""


class PoolSnapshotTaskUpdate(PoolSnapshotTaskCreate, metaclass=ForUpdateMetaclass):
    fixate_removal_date: bool
    """Whether to fix the removal date of existing snapshots when retention settings change."""


class PoolSnapshotTaskUpdateWillChangeRetentionFor(PoolSnapshotTaskCreate, metaclass=ForUpdateMetaclass):
    pass


class PoolSnapshotTaskDeleteOptions(BaseModel):
    fixate_removal_date: bool = False
    """Whether to fix the removal date of existing snapshots when the task is deleted."""


class PoolSnapshotTaskDBEntry(PoolSnapshotTaskCreate):
    id: int
    """Unique identifier for the periodic snapshot task."""
    state: str
    """Current state of the task."""


class PeriodicSnapshotTaskEntry(PoolSnapshotTaskDBEntry):
    vmware_sync: bool
    """Whether VMware VMs are synced before taking snapshots."""
    state: Any
    """Detailed state information for the task."""


class PeriodicSnapshotTaskCreateArgs(BaseModel):
    data: PoolSnapshotTaskCreate
    """Configuration for the new periodic snapshot task."""


class PeriodicSnapshotTaskCreateResult(BaseModel):
    result: PeriodicSnapshotTaskEntry
    """The newly created periodic snapshot task configuration."""


class PeriodicSnapshotTaskUpdateArgs(BaseModel):
    id: int
    """ID of the periodic snapshot task to update."""
    data: PoolSnapshotTaskUpdate
    """Updated configuration for the periodic snapshot task."""


class PeriodicSnapshotTaskUpdateResult(BaseModel):
    result: PeriodicSnapshotTaskEntry
    """The updated periodic snapshot task configuration."""


class PeriodicSnapshotTaskDeleteArgs(BaseModel):
    id: int
    """ID of the periodic snapshot task to delete."""
    options: PoolSnapshotTaskDeleteOptions = Field(default_factory=PoolSnapshotTaskDeleteOptions)
    """Options for controlling task deletion behavior."""


class PeriodicSnapshotTaskDeleteResult(BaseModel):
    result: Literal[True]
    """Indicates successful deletion of the periodic snapshot task."""


class PeriodicSnapshotTaskMaxCountArgs(BaseModel):
    pass


class PeriodicSnapshotTaskMaxCountResult(BaseModel):
    result: int
    """Maximum number of periodic snapshot tasks allowed."""


class PeriodicSnapshotTaskMaxTotalCountArgs(BaseModel):
    pass


class PeriodicSnapshotTaskMaxTotalCountResult(BaseModel):
    result: int
    """Maximum total number of snapshots allowed across all tasks."""


class PeriodicSnapshotTaskRunArgs(BaseModel):
    id: int
    """ID of the periodic snapshot task to run immediately."""


class PeriodicSnapshotTaskRunResult(BaseModel):
    result: None
    """Returns `null` on successful task execution."""


class PeriodicSnapshotTaskUpdateWillChangeRetentionForArgs(BaseModel):
    id: int
    """ID of the periodic snapshot task to analyze."""
    data: PoolSnapshotTaskUpdateWillChangeRetentionFor
    """Proposed configuration changes to analyze."""


class PeriodicSnapshotTaskUpdateWillChangeRetentionForResult(BaseModel):
    result: dict[str, list[str]]
    """Object mapping retention change types to arrays of affected snapshot names."""


class PeriodicSnapshotTaskDeleteWillChangeRetentionForArgs(BaseModel):
    id: int
    """ID of the periodic snapshot task to analyze for deletion impact."""


class PeriodicSnapshotTaskDeleteWillChangeRetentionForResult(BaseModel):
    result: dict[str, list[str]]
    """Object mapping retention change types to arrays of snapshots that would be affected by task deletion."""
