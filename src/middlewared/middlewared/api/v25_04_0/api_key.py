from datetime import datetime
from typing import Annotated, Literal

from middlewared.api.base import BaseModel, NonEmptyString

__all__ = ["ApiKeyCreateArgs", "ApiKeyCreateResult"]


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
