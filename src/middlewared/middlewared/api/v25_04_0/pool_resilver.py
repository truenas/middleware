from typing import Annotated

from pydantic import Field

from middlewared.api.base import BaseModel, TimeString, ForUpdateMetaclass


__all__ = ["PoolResilverEntry", "PoolResilverUpdateArgs", "PoolResilverUpdateResult"]


class PoolResilverEntry(BaseModel):
    id: int
    begin: TimeString
    end: TimeString
    enabled: bool
    weekday: list[Annotated[int, Field(ge=1, le=7)]]


class PoolResilverUpdate(PoolResilverEntry, metaclass=ForUpdateMetaclass):
    pass


class PoolResilverUpdateArgs(BaseModel):
    data: PoolResilverUpdate


class PoolResilverUpdateResult(BaseModel):
    result: PoolResilverEntry
