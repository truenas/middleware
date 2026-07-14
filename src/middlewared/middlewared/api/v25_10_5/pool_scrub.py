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
    minute: str = Field(default="00", description="Minute when the scrub should run (cron format).")
    hour: str = Field(default="00", description="Hour when the scrub should run (cron format).")
    dow: str = Field(default="7", description="Day of week when the scrub should run (cron format, 7=Sunday).")


class PoolScrubEntry(BaseModel):
    pool: PositiveInt = Field(description="ID of the pool to scrub.")
    threshold: Annotated[int, Field(ge=0)] = Field(
        default=35,
        description="Days before a scrub is due when a scrub should automatically start.",
    )
    description: str = Field(default="", description="Description or notes for this scrub schedule.")
    schedule: PoolScrubCron = Field(
        default_factory=PoolScrubCron,
        description="Cron schedule for when scrubs should run.",
    )
    enabled: bool = Field(default=True, description="Whether this scrub schedule is enabled.")
    id: int = Field(description="Unique identifier for the scrub schedule.")
    pool_name: str = Field(description="Name of the pool being scrubbed.")


class PoolScrubCreate(PoolScrubEntry):
    id: Excluded = excluded_field()
    pool_name: Excluded = excluded_field()


class PoolScrubUpdate(PoolScrubCreate, metaclass=ForUpdateMetaclass):
    pass


class PoolScrubCreateArgs(BaseModel):
    data: PoolScrubCreate = Field(description="Configuration for the new scrub schedule.")


class PoolScrubCreateResult(BaseModel):
    result: PoolScrubEntry = Field(description="The newly created scrub schedule configuration.")


class PoolScrubUpdateArgs(BaseModel):
    id_: int = Field(description="ID of the scrub schedule to update.")
    data: PoolScrubUpdate = Field(description="Updated configuration for the scrub schedule.")


class PoolScrubUpdateResult(BaseModel):
    result: PoolScrubEntry = Field(description="The updated scrub schedule configuration.")


class PoolScrubDeleteArgs(BaseModel):
    id_: int = Field(description="ID of the scrub schedule to delete.")


class PoolScrubDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Indicates successful deletion of the scrub schedule.")


class PoolScrubScrubArgs(BaseModel):
    name: str = Field(description="Name of the pool to perform scrub action on.")
    action: Literal["START", "STOP", "PAUSE"] = Field(
        default="START",
        description="The scrub action to perform on the pool.",
    )


class PoolScrubScrubResult(BaseModel):
    result: None = Field(description="Returns `null` on successful scrub action.")


class PoolScrubRunArgs(BaseModel):
    name: str = Field(description="Name of the pool to run scrub on.")
    threshold: int = Field(default=35, description="Days before a scrub is due when the scrub should start.")


class PoolScrubRunResult(BaseModel):
    result: None = Field(description="Returns `null` on successful scrub start.")
