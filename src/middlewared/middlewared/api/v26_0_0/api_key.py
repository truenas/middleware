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
    "ApiKeyConvertRawKeyArgs", "ApiKeyConvertRawKeyResult",
]


class AllowListItem(BaseModel):
    method: HttpVerb = Field(description="Method allowed for this API endpoint.")
    resource: NonEmptyString = Field(description="API resource path or endpoint this permission applies to.")


class ApiKeyEntry(BaseModel):
    id: int = Field(description="Unique identifier for the API key.")
    name: NonEmptyString = Field(max_length=200, description="Human-readable name for the API key.")
    username: LocalUsername | RemoteUsername | None = Field(
        description="Username associated with the API key or `null` for system keys.",
    )
    user_identifier: int | str = Field(description="User ID (numeric) or SID (string) that owns this API key.")
    iterations: int = Field(description="Number of iterations of PBKDF2-SHA512.")
    salt: Secret[str] = Field(description="Base64 encoded salt for API key.")
    stored_key: Secret[str] = Field(description="SCRAM StoredKey for API key.")
    server_key: Secret[str] = Field(description="SCRAM ServerKey for API key.")
    created_at: datetime = Field(description="Timestamp when the API key was created.")
    expires_at: datetime | None = Field(
        default=None,
        description="Expiration timestamp for the API key or `null` for no expiration.",
    )
    local: bool = Field(description="Whether this API key is for local system use only.")
    revoked: bool = Field(description="Whether the API key has been revoked and is no longer valid.")
    revoked_reason: str | None = Field(description="Reason for API key revocation or `null` if not revoked.")


class ApiKeyEntryWithKey(ApiKeyEntry):
    key: str = Field(description="The actual API key value (only returned on creation).")
    client_key: str = Field(description="Pre-computed SCRAM ClientKey.")


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
    api_key_create: ApiKeyCreate = Field(description="API key configuration data for the new key.")


class ApiKeyCreateResult(BaseModel):
    result: ApiKeyEntryWithKey = Field(description="The created API key with the actual key value.")


class ApiKeyUpdate(ApiKeyCreate, metaclass=ForUpdateMetaclass):
    username: Excluded = excluded_field()
    reset: bool = Field(description="Whether to regenerate a new API key value for this entry.")


class ApiKeyUpdateArgs(BaseModel):
    id: int = Field(description="ID of the API key to update.")
    api_key_update: ApiKeyUpdate = Field(description="Updated API key configuration data.")


class ApiKeyUpdateResult(BaseModel):
    result: ApiKeyEntryWithKey | ApiKeyEntry = Field(
        description="The updated API key (includes key value if reset was performed).",
    )


class ApiKeyDeleteArgs(BaseModel):
    id: int = Field(description="ID of the API key to delete.")


class ApiKeyDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the API key is successfully deleted.")


class ApiKeyMyKeysArgs(BaseModel):
    pass


class ApiKeyMyKeysResult(BaseModel):
    result: list[ApiKeyEntry] = Field(description="Array of API keys owned by the current authenticated user.")


class ApiKeyConvertRawKeyArgs(BaseModel):
    raw_key: Secret[NonEmptyString] = Field(description="The raw API key to convert (format: id-key).")


class ApiKeyScramData(BaseModel):
    api_key_id: int = Field(description="API key ID.")
    iterations: int = Field(description="Number of iterations of PBKDF2-SHA512.")
    salt: str = Field(description="Base64 encoded salt for API key.")
    client_key: str = Field(description="Pre-computed SCRAM ClientKey.")
    stored_key: str = Field(description="SCRAM StoredKey for API key.")
    server_key: str = Field(description="SCRAM ServerKey for API key.")


class ApiKeyConvertRawKeyResult(BaseModel):
    result: ApiKeyScramData = Field(description="SCRAM authentication data derived from the raw API key.")
