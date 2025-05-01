from typing import Literal

from middlewared.api.base import BaseModel, ForUpdateMetaclass
from .common import CronModel


__all__ = [
    "CronJobEntry", "CronJobCreateArgs", "CronJobCreateResult", "CronJobUpdateArgs", "CronJobUpdateResult",
    "CronJobDeleteArgs", "CronJobDeleteResult", "CronJobRunArgs", "CronJobRunResult"
]


class CronJobSchedule(CronModel):
    minute: str = "00"


class CronJobCreate(BaseModel):
    enabled: bool = True
    stderr: bool = False
    stdout: bool = True
    schedule: CronJobSchedule = CronJobSchedule()
    command: str
    description: str = ""
    user: str


class CronJobEntry(CronJobCreate):
    id: int


class CronJobUpdate(CronJobCreate, metaclass=ForUpdateMetaclass):
    pass


class CronJobCreateArgs(BaseModel):
    data: CronJobCreate


class CronJobCreateResult(BaseModel):
    result: CronJobEntry


class CronJobUpdateArgs(BaseModel):
    id: int
    data: CronJobUpdate


class CronJobUpdateResult(BaseModel):
    result: CronJobEntry


class CronJobDeleteArgs(BaseModel):
    id: int


class CronJobDeleteResult(BaseModel):
    result: Literal[True]


class CronJobRunArgs(BaseModel):
    id: int
    skip_disabled: bool = False


class CronJobRunResult(BaseModel):
    result: None
