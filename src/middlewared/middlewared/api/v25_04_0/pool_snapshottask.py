from typing import Annotated, Any, Literal

from pydantic import AfterValidator, Field

from middlewared.api.base import BaseModel, ForUpdateMetaclass, TimeString
from middlewared.validators import ReplicationSnapshotNamingSchema
from .common import CronModel


__all__ = [
    "PoolSnapshotTaskEntry", "PoolSnapshotTaskCreateArgs", "PoolSnapshotTaskCreateResult",
    "PoolSnapshotTaskUpdateArgs", "PoolSnapshotTaskUpdateResult", "PoolSnapshotTaskDeleteArgs",
    "PoolSnapshotTaskDeleteResult", "PoolSnapshotTaskMaxCountArgs", "PoolSnapshotTaskMaxCountResult",
    "PoolSnapshotTaskMaxTotalCountArgs", "PoolSnapshotTaskMaxTotalCountResult", "PoolSnapshotTaskRunArgs",
    "PoolSnapshotTaskRunResult", "PoolSnapshotTaskUpdateWillChangeRetentionForArgs",
    "PoolSnapshotTaskUpdateWillChangeRetentionForResult", "PoolSnapshotTaskDeleteWillChangeRetentionForArgs",
    "PoolSnapshotTaskDeleteWillChangeRetentionForResult"
]


SnapshotNameSchema = Annotated[str, AfterValidator(ReplicationSnapshotNamingSchema())]


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


class PoolSnapshotTaskEntry(PoolSnapshotTaskCreate):
    id: int
    vmware_sync: bool
    state: Any


class PoolSnapshotTaskCreateArgs(BaseModel):
    data: PoolSnapshotTaskCreate


class PoolSnapshotTaskCreateResult(BaseModel):
    result: PoolSnapshotTaskEntry


class PoolSnapshotTaskUpdateArgs(BaseModel):
    id: int
    data: PoolSnapshotTaskUpdate


class PoolSnapshotTaskUpdateResult(BaseModel):
    result: PoolSnapshotTaskEntry


class PoolSnapshotTaskDeleteArgs(BaseModel):
    id: int
    options: PoolSnapshotTaskDeleteOptions = Field(default_factory=PoolSnapshotTaskDeleteOptions)


class PoolSnapshotTaskDeleteResult(BaseModel):
    result: Literal[True]


class PoolSnapshotTaskMaxCountArgs(BaseModel):
    pass


class PoolSnapshotTaskMaxCountResult(BaseModel):
    result: Literal[512]


class PoolSnapshotTaskMaxTotalCountArgs(BaseModel):
    pass


class PoolSnapshotTaskMaxTotalCountResult(BaseModel):
    result: Literal[10000]


class PoolSnapshotTaskRunArgs(BaseModel):
    id: int


class PoolSnapshotTaskRunResult(BaseModel):
    result: None


class PoolSnapshotTaskUpdateWillChangeRetentionForArgs(BaseModel):
    id: int
    data: PoolSnapshotTaskUpdateWillChangeRetentionFor


class PoolSnapshotTaskUpdateWillChangeRetentionForResult(BaseModel):
    result: dict[str, list[str]]


class PoolSnapshotTaskDeleteWillChangeRetentionForArgs(BaseModel):
    id: int


class PoolSnapshotTaskDeleteWillChangeRetentionForResult(BaseModel):
    result: dict[str, list[str]]
