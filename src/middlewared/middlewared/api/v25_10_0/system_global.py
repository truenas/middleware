from middlewared.api.base import BaseModel

__all__ = ("SystemGlobalIdArgs", "SystemGlobalIdResult")


class SystemGlobalIdArgs(BaseModel):
    pass


class SystemGlobalIdResult(BaseModel):
    result: str
