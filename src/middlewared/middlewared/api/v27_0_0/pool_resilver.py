from typing import Annotated

from pydantic import Field

from middlewared.api.base import BaseModel, TimeString, ForUpdateMetaclass, Excluded, excluded_field


__all__ = ["PoolResilverEntry", "PoolResilverUpdateArgs", "PoolResilverUpdateResult"]


class PoolResilverEntry(BaseModel):
    id: int
    """Unique identifier for the resilver schedule entry."""
    begin: TimeString = "18:00"
    """Time when the resilver operations window begins (24-hour format)."""
    end: TimeString = "9:00"
    """Time when the resilver operations window ends (24-hour format)."""
    enabled: bool = True
    """Whether the resilver schedule is enabled."""
    weekday: list[Annotated[int, Field(ge=1, le=7)]] = list(range(1, 8))
    """Array of weekdays when resilver operations are allowed (1=Monday through 7=Sunday)."""


class PoolResilverUpdate(PoolResilverEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class PoolResilverUpdateArgs(BaseModel):
    data: PoolResilverUpdate
    """The resilver schedule configuration to update."""


class PoolResilverUpdateResult(BaseModel):
    result: PoolResilverEntry
    """The updated resilver schedule configuration."""
