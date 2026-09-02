from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, Secret

from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    NonEmptyString,
    LocalUsername,
    RemoteUsername,
)


__all__ = [
    "S3AccesskeyEntry",
    "S3AccesskeyCreate",
    "S3AccesskeyUpdate",
    "S3AccesskeyCreateArgs",
    "S3AccesskeyCreateResult",
    "S3AccesskeyUpdateArgs",
    "S3AccesskeyUpdateResult",
    "S3AccesskeyDeleteArgs",
    "S3AccesskeyDeleteResult",
]

S3AccessKeyId = Annotated[str, Field(pattern=r"^[A-Z0-9]{16,128}$")]
"""An S3 access key id. Uppercase alphanumerics only, so it is safe inside
the quoted section heading of the S3 service's credentials file."""

S3SecretKey = Annotated[str, Field(min_length=16, max_length=128, pattern=r"^[\x21-\x7E]+$")]
"""An S3 secret access key. Printable ASCII with no whitespace, so the
value survives the S3 service's whitespace-trimming config reader."""

S3AccesskeyStatus = Literal["ENABLED", "DISABLED", "EXPIRED", "USER_MISSING", "SECRET_LOST"]


class S3AccesskeyEntry(BaseModel):
    id: int = Field(description="Unique identifier for the access key.")
    name: NonEmptyString = Field(max_length=200, description="Human-readable name for the access key.")
    username: LocalUsername | RemoteUsername | None = Field(
        description="Account the access key belongs to, or `null` if that account no longer exists.",
    )
    user_identifier: int | str = Field(
        description=(
            "Stored account linkage. A numeric user ID for local accounts or a SID for directory services accounts."
        ),
    )
    local: bool = Field(
        description="Whether the access key belongs to a local user account rather than a directory services one.",
    )
    access_key: S3AccessKeyId = Field(description="The S3 access key id clients sign requests with.")
    secret: Secret[str | None] = Field(
        description=(
            "The S3 secret access key. Readable only by administrators holding `SHARING_S3_WRITE`; redacted for "
            "everyone else. `null` when the secret was lost to a configuration restore without the secret seed."
        ),
    )
    enabled: bool = Field(
        description="Whether the access key may be used. A disabled key is refused by the S3 service."
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Expiration timestamp for the access key or `null` for no expiration.",
    )
    created_at: datetime = Field(description="Timestamp when the access key was created.")
    status: S3AccesskeyStatus = Field(
        description=(
            "Effective state of the access key. Only `ENABLED` keys are usable. `DISABLED` was set by an "
            "administrator, `EXPIRED` passed its expiration, `USER_MISSING` belongs to an account that no longer "
            "exists, and `SECRET_LOST` lost its secret to a configuration restore without the secret seed and "
            "must be rotated."
        ),
    )


class S3AccesskeyCreate(S3AccesskeyEntry):
    id: Excluded = excluded_field()
    username: LocalUsername | RemoteUsername = Field(description="Account the access key belongs to.")
    user_identifier: Excluded = excluded_field()
    local: Excluded = excluded_field()
    access_key: S3AccessKeyId | None = Field(
        default=None,
        description="Access key id for the new key. Generated when omitted.",
    )
    secret: Secret[S3SecretKey | None] = Field(
        default=None,
        description="Secret access key for the new key. Generated when omitted.",
    )
    enabled: bool = Field(default=True, description="Whether the access key may be used.")
    created_at: Excluded = excluded_field()
    status: Excluded = excluded_field()


class S3AccesskeyCreateArgs(BaseModel):
    data: S3AccesskeyCreate = Field(description="Configuration for the new access key.")


class S3AccesskeyCreateResult(BaseModel):
    result: S3AccesskeyEntry = Field(description="The created access key, including its secret.")


class S3AccesskeyUpdate(S3AccesskeyCreate, metaclass=ForUpdateMetaclass):
    username: Excluded = excluded_field()
    access_key: Excluded = excluded_field()
    secret: Excluded = excluded_field()
    rotate: bool = Field(
        default=False,
        description="Generate a new secret access key under the same access key id.",
    )


class S3AccesskeyUpdateArgs(BaseModel):
    id: int = Field(description="ID of the access key to update.")
    data: S3AccesskeyUpdate = Field(description="Access key changes to apply.")


class S3AccesskeyUpdateResult(BaseModel):
    result: S3AccesskeyEntry = Field(description="The updated access key, including its secret.")


class S3AccesskeyDeleteArgs(BaseModel):
    id: int = Field(description="ID of the access key to delete.")


class S3AccesskeyDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the access key is successfully deleted.")
