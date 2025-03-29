from middlewared.api.base import BaseModel

__all__ = (
    "SystemGlobalIdEntry",
    "SystemGlobalIdArgs",
    "SystemGlobalIdResult"
)


class SystemGlobalIdEntry(BaseModel):
    id: int
    system_uuid: str


class SystemGlobalIdArgs(BaseModel):
    pass


class SystemGlobalIdResult(BaseModel):
    result: SystemGlobalIdEntry
