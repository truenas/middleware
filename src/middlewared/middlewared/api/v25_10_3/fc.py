from middlewared.api.base import BaseModel


__all__ = ["FCCapableArgs", "FCCapableResult",]


class FCCapableArgs(BaseModel):
    pass


class FCCapableResult(BaseModel):
    result: bool
    """Returns `true` if the system has Fibre Channel capabilities, `false` otherwise."""
