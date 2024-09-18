from datetime import datetime
from typing import Literal, TypeAlias
from typing_extensions import Annotated

from pydantic import StringConstraints

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, Private,
    LocalUsername, RemoteUsername
)


HttpVerb: TypeAlias = Literal["GET", "POST", "PUT", "DELETE", "CALL", "SUBSCRIBE", "*"]


class AllowListItem(BaseModel):
    method: HttpVerb
    resource: NonEmptyString


class ApiKeyEntry(BaseModel):
    id: int
    name: Annotated[NonEmptyString, StringConstraints(max_length=200)]
    username: LocalUsername | RemoteUsername
    created_at: datetime
    expires_at: datetime | None = None
    local: bool
    revoked: bool


class ApiKeyEntryWithKey(ApiKeyEntry):
    key: Private[str]


class ApiKeyCreate(ApiKeyEntry):
    id: Excluded = excluded_field()
    created_at: Excluded = excluded_field()
    local: Excluded = excluded_field()
    revoked: Excluded = excluded_field()


class ApiKeyCreateArgs(BaseModel):
    api_key_create: ApiKeyCreate


class ApiKeyCreateResult(BaseModel):
    result: ApiKeyEntryWithKey


class ApiKeyUpdate(ApiKeyCreate, metaclass=ForUpdateMetaclass):
    username: Excluded = excluded_field()
    reset: bool


class ApiKeyUpdateArgs(BaseModel):
    id: int
    api_key_update: ApiKeyUpdate


class ApiKeyUpdateResult(BaseModel):
    result: ApiKeyEntryWithKey


class ApiKeyDeleteArgs(BaseModel):
    id: int


class ApiKeyDeleteResult(BaseModel):
    result: Literal[True]
