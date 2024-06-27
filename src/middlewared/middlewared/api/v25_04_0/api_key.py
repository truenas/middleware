from datetime import datetime
from typing import Literal

from middlewared.api.base import BaseModel, NonEmptyString

__all__ = [
    "ApiKeyCreateArgs",
    "ApiKeyCreateResult",
    "ApiKeyUpdateArgs",
    "ApiKeyUpdateResult",
    "ApiKeyDeleteArgs",
    "ApiKeyDeleteResult",
]


class AllowListItem(BaseModel):
    method: Literal["GET", "POST", "PUT", "DELETE", "CALL", "SUBSCRIBE", "*"]
    resource: NonEmptyString


class ApiKeyCreate(BaseModel):
    name: NonEmptyString
    allowlist: list[AllowListItem]


class ApiKeyCreateArgs(BaseModel):
    api_key_create: ApiKeyCreate


class ApiKeyCreateResult(ApiKeyCreate):
    id: str
    key: str
    created_at: datetime


class ApiKeyUpdate(ApiKeyCreate):
    reset: bool
    update: bool = True


class ApiKeyUpdateArgs(BaseModel):
    id: int
    api_key_update: ApiKeyUpdate


class ApiKeyUpdateResult(BaseModel):
    # Needs implemented
    pass


class ApiKeyDeleteArgs(BaseModel):
    id: int


class ApiKeyDeleteResult(BaseModel):
    # Needs implemented
    pass