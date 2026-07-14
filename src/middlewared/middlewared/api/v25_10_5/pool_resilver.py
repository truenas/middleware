from typing import Annotated

from pydantic import Field

from middlewared.api.base import BaseModel, TimeString, ForUpdateMetaclass, Excluded, excluded_field


__all__ = ["PoolResilverEntry", "PoolResilverUpdateArgs", "PoolResilverUpdateResult"]


class PoolResilverEntry(BaseModel):
    id: int = Field(description="Unique identifier for the resilver schedule entry.")
    begin: TimeString = Field(
        default="18:00",
        description="Time when the resilver operations window begins (24-hour format).",
    )
    end: TimeString = Field(
        default="9:00",
        description="Time when the resilver operations window ends (24-hour format).",
    )
    enabled: bool = Field(default=True, description="Whether the resilver schedule is enabled.")
    weekday: list[Annotated[int, Field(ge=1, le=7)]] = Field(
        default=list(range(1, 8)),
        description="Array of weekdays when resilver operations are allowed (1=Monday through 7=Sunday).",
    )


class PoolResilverUpdate(PoolResilverEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class PoolResilverUpdateArgs(BaseModel):
    data: PoolResilverUpdate = Field(description="The resilver schedule configuration to update.")


class PoolResilverUpdateResult(BaseModel):
    result: PoolResilverEntry = Field(description="The updated resilver schedule configuration.")
