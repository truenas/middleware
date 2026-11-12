from pydantic import Field

from middlewared.api.base import BaseModel


__all__ = ["FCCapableArgs", "FCCapableResult",]


class FCCapableArgs(BaseModel):
    pass


class FCCapableResult(BaseModel):
    result: bool = Field(description="Returns `true` if the system has Fibre Channel capabilities, `false` otherwise.")
