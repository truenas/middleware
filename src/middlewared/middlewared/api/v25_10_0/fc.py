from middlewared.api.base import BaseModel


__all__ = ["FCCapableArgs", "FCCapableResult",]


class FCCapableArgs(BaseModel):
    pass


class FCCapableResult(BaseModel):
    result: bool
