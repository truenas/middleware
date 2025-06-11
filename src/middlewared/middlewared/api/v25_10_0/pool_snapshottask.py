from typing import Any, Literal

from pydantic import Field

from middlewared.api.base import BaseModel, ForUpdateMetaclass, TimeString, SnapshotNameSchema
from .common import CronModel


__all__ = [
    "PoolSnapshotTaskDBEntry", "PoolSnapshotTaskEntry", "PeriodicSnapshotTaskCreateArgs", "PeriodicSnapshotTaskCreateResult",
    "PeriodicSnapshotTaskUpdateArgs", "PeriodicSnapshotTaskUpdateResult", "PeriodicSnapshotTaskDeleteArgs",
    "PeriodicSnapshotTaskDeleteResult", "PeriodicSnapshotTaskMaxCountArgs", "PeriodicSnapshotTaskMaxCountResult",
    "PeriodicSnapshotTaskMaxTotalCountArgs", "PeriodicSnapshotTaskMaxTotalCountResult", "PeriodicSnapshotTaskRunArgs",
    "PeriodicSnapshotTaskRunResult", "PeriodicSnapshotTaskUpdateWillChangeRetentionForArgs",
    "PeriodicSnapshotTaskUpdateWillChangeRetentionForResult", "PeriodicSnapshotTaskDeleteWillChangeRetentionForArgs",
    "PeriodicSnapshotTaskDeleteWillChangeRetentionForResult"
]


class PoolSnapshotTaskCron(CronModel):
    minute: str = "00"
    begin: TimeString = "00:00"
    end: TimeString = "23:59"


class PoolSnapshotTaskCreate(BaseModel):
    dataset: str
    recursive: bool = False
    lifetime_value: int = 2
    lifetime_unit: Literal["HOUR", "DAY", "WEEK", "MONTH", "YEAR"] = "WEEK"
    enabled: bool = True
    exclude: list[str] = []
    naming_schema: SnapshotNameSchema = "auto-%Y-%m-%d_%H-%M"
    allow_empty: bool = True
    schedule: PoolSnapshotTaskCron = Field(default_factory=PoolSnapshotTaskCron)


class PoolSnapshotTaskUpdate(PoolSnapshotTaskCreate, metaclass=ForUpdateMetaclass):
    fixate_removal_date: bool


class PoolSnapshotTaskUpdateWillChangeRetentionFor(PoolSnapshotTaskCreate, metaclass=ForUpdateMetaclass):
    pass


class PoolSnapshotTaskDeleteOptions(BaseModel):
    fixate_removal_date: bool = False


class PoolSnapshotTaskDBEntry(PoolSnapshotTaskCreate):
    id: int
    state: str


class PoolSnapshotTaskEntry(PoolSnapshotTaskDBEntry):
    vmware_sync: bool
    state: Any


class PeriodicSnapshotTaskCreateArgs(BaseModel):
    data: PoolSnapshotTaskCreate


class PeriodicSnapshotTaskCreateResult(BaseModel):
    result: PoolSnapshotTaskEntry


class PeriodicSnapshotTaskUpdateArgs(BaseModel):
    id: int
    data: PoolSnapshotTaskUpdate


class PeriodicSnapshotTaskUpdateResult(BaseModel):
    result: PoolSnapshotTaskEntry


class PeriodicSnapshotTaskDeleteArgs(BaseModel):
    id: int
    options: PoolSnapshotTaskDeleteOptions = Field(default_factory=PoolSnapshotTaskDeleteOptions)


class PeriodicSnapshotTaskDeleteResult(BaseModel):
    result: Literal[True]


class PeriodicSnapshotTaskMaxCountArgs(BaseModel):
    pass


class PeriodicSnapshotTaskMaxCountResult(BaseModel):
    result: int


class PeriodicSnapshotTaskMaxTotalCountArgs(BaseModel):
    pass


class PeriodicSnapshotTaskMaxTotalCountResult(BaseModel):
    result: int


class PeriodicSnapshotTaskRunArgs(BaseModel):
    id: int


class PeriodicSnapshotTaskRunResult(BaseModel):
    result: None


class PeriodicSnapshotTaskUpdateWillChangeRetentionForArgs(BaseModel):
    id: int
    data: PoolSnapshotTaskUpdateWillChangeRetentionFor


class PeriodicSnapshotTaskUpdateWillChangeRetentionForResult(BaseModel):
    result: dict[str, list[str]]


class PeriodicSnapshotTaskDeleteWillChangeRetentionForArgs(BaseModel):
    id: int


class PeriodicSnapshotTaskDeleteWillChangeRetentionForResult(BaseModel):
    result: dict[str, list[str]]
