from datetime import datetime
from typing import Literal

from pydantic import Secret, Field

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString,
    LocalUsername, RemoteUsername, HttpVerb,
)


__all__ = [
    "ApiKeyEntry", "ApiKeyCreateArgs", "ApiKeyCreateResult", "ApiKeyUpdateArgs", "ApiKeyUpdateResult",
    "ApiKeyDeleteArgs", "ApiKeyDeleteResult", "ApiKeyMyKeysArgs", "ApiKeyMyKeysResult",
]


class AllowListItem(BaseModel):
    method: HttpVerb
    """Method allowed for this API endpoint."""
    resource: NonEmptyString
    """API resource path or endpoint this permission applies to."""


class ApiKeyEntry(BaseModel):
    id: int
    """Unique identifier for the API key."""
    name: NonEmptyString = Field(max_length=200)
    """Human-readable name for the API key."""
    username: LocalUsername | RemoteUsername | None
    """Username associated with the API key or `null` for system keys."""
    user_identifier: int | str
    """User ID (numeric) or SID (string) that owns this API key."""
    iterations: int
    """Number of iterations of PBKDF2-SHA512."""
    salt: Secret[str]
    """Base64 encoded salt for API key."""
    stored_key: Secret[str]
    """SCRAM StoredKey for API key."""
    server_key: Secret[str]
    """SCRAM ServerKey for API key."""
    created_at: datetime
    """Timestamp when the API key was created."""
    expires_at: datetime | None = None
    """Expiration timestamp for the API key or `null` for no expiration."""
    local: bool
    """Whether this API key is for local system use only."""
    revoked: bool
    """Whether the API key has been revoked and is no longer valid."""
    revoked_reason: str | None
    """Reason for API key revocation or `null` if not revoked."""


class ApiKeyEntryWithKey(ApiKeyEntry):
    key: str
    """The actual API key value (only returned on creation)."""
    client_key: str
    """Pre-computed SCRAM ClientKey."""


class ApiKeyCreate(ApiKeyEntry):
    id: Excluded = excluded_field()
    username: LocalUsername | RemoteUsername
    user_identifier: Excluded = excluded_field()
    salt: Excluded = excluded_field()
    stored_key: Excluded = excluded_field()
    server_key: Excluded = excluded_field()
    iterations: Excluded = excluded_field()
    created_at: Excluded = excluded_field()
    local: Excluded = excluded_field()
    revoked: Excluded = excluded_field()
    revoked_reason: Excluded = excluded_field()


class ApiKeyCreateArgs(BaseModel):
    api_key_create: ApiKeyCreate
    """API key configuration data for the new key."""


class ApiKeyCreateResult(BaseModel):
    result: ApiKeyEntryWithKey
    """The created API key with the actual key value."""


class ApiKeyUpdate(ApiKeyCreate, metaclass=ForUpdateMetaclass):
    username: Excluded = excluded_field()
    reset: bool
    """Whether to regenerate a new API key value for this entry."""


class ApiKeyUpdateArgs(BaseModel):
    id: int
    """ID of the API key to update."""
    api_key_update: ApiKeyUpdate
    """Updated API key configuration data."""


class ApiKeyUpdateResult(BaseModel):
    result: ApiKeyEntryWithKey | ApiKeyEntry
    """The updated API key (includes key value if reset was performed)."""


class ApiKeyDeleteArgs(BaseModel):
    id: int
    """ID of the API key to delete."""


class ApiKeyDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the API key is successfully deleted."""


class ApiKeyMyKeysArgs(BaseModel):
    pass


class ApiKeyMyKeysResult(BaseModel):
    result: list[ApiKeyEntry]
    """Array of API keys owned by the current authenticated user."""
