from pydantic import Field

from middlewared.api.base import BaseModel

__all__ = ("SystemGlobalIDIdArgs", "SystemGlobalIDIdResult")


class SystemGlobalIDIdArgs(BaseModel):
    pass


class SystemGlobalIDIdResult(BaseModel):
    result: str = Field(description="Unique system identifier.")
