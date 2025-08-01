from middlewared.api.base import BaseModel

__all__ = ("SystemGlobalIDIdArgs", "SystemGlobalIDIdResult")


class SystemGlobalIDIdArgs(BaseModel):
    pass


class SystemGlobalIDIdResult(BaseModel):
    result: str
    """Unique system identifier."""
