from typing import Annotated, Literal

from pydantic import Field, PositiveInt

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass
from .common import CronModel


__all__ = [
    "PoolScrubEntry", "PoolScrubCreateArgs", "PoolScrubCreateResult", "PoolScrubUpdateArgs", "PoolScrubUpdateResult",
    "PoolScrubDeleteArgs", "PoolScrubDeleteResult", "PoolScrubScrubArgs", "PoolScrubScrubResult", "PoolScrubRunArgs",
    "PoolScrubRunResult"
]


class PoolScrubCron(CronModel):
    minute: str = "00"
    hour: str = "00"
    dow: str = "7"


class PoolScrubEntry(BaseModel):
    pool: PositiveInt
    threshold: Annotated[int, Field(ge=0)] = 35
    description: str = ""
    schedule: PoolScrubCron = Field(default_factory=PoolScrubCron)
    enabled: bool = True
    id: int
    pool_name: str


class PoolScrubCreate(PoolScrubEntry):
    id: Excluded = excluded_field()
    pool_name: Excluded = excluded_field()


class PoolScrubUpdate(PoolScrubCreate, metaclass=ForUpdateMetaclass):
    pass


class PoolScrubCreateArgs(BaseModel):
    data: PoolScrubCreate


class PoolScrubCreateResult(BaseModel):
    result: PoolScrubEntry


class PoolScrubUpdateArgs(BaseModel):
    id_: int
    data: PoolScrubUpdate


class PoolScrubUpdateResult(BaseModel):
    result: PoolScrubEntry


class PoolScrubDeleteArgs(BaseModel):
    id_: int


class PoolScrubDeleteResult(BaseModel):
    result: Literal[True]


class PoolScrubScrubArgs(BaseModel):
    name: str
    action: Literal["START", "STOP", "PAUSE"] = "START"


class PoolScrubScrubResult(BaseModel):
    result: None


class PoolScrubRunArgs(BaseModel):
    name: str
    threshold: int = 35


class PoolScrubRunResult(BaseModel):
    result: None
