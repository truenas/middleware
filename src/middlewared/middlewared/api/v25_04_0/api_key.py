from datetime import datetime
from typing import Literal, TypeAlias
from typing_extensions import Annotated

from pydantic import ConfigDict, StringConstraints

from middlewared.api.base import BaseModel, Excluded, excluded_field, NonEmptyString, Private


HttpVerb: TypeAlias = Literal["GET", "POST", "PUT", "DELETE", "CALL", "SUBSCRIBE", "*"]


class AllowListItem(BaseModel):
    method: HttpVerb
    resource: NonEmptyString


class ApiKeyEntry(BaseModel):
    """Represents a record in the account.api_key table."""

    id: int
    name: Annotated[NonEmptyString, StringConstraints(max_length=200)]
    key: Private[str]
    created_at: datetime
    allowlist: list[AllowListItem]


class ApiKeyCreate(ApiKeyEntry):
    id: Excluded = excluded_field()
    key: Excluded = excluded_field()
    created_at: Excluded = excluded_field()


class ApiKeyCreateArgs(BaseModel):
    api_key_create: ApiKeyCreate


class ApiKeyCreateResult(BaseModel):
    result: ApiKeyEntry


class ApiKeyUpdate(ApiKeyCreate):
    reset: bool


class ApiKeyUpdateArgs(BaseModel):
    id: int
    api_key_update: ApiKeyUpdate


class ApiKeyUpdateResult(BaseModel):
    result: ApiKeyEntry


class ApiKeyDeleteArgs(BaseModel):
    id: int


class ApiKeyDeleteResult(BaseModel):
    result: Literal[True]
