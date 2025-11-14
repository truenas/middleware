from pydantic import Secret

from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongString, NonEmptyString,
                                  single_argument_args, single_argument_result)

__all__ = ["CredentialsEntry",
           "CredentialsCreateArgs", "CredentialsCreateResult",
           "CredentialsUpdateArgs", "CredentialsUpdateResult",
           "CredentialsDeleteArgs", "CredentialsDeleteResult",
           "CredentialsVerifyArgs", "CredentialsVerifyResult"]


class CredentialsEntry(BaseModel):
    id: int
    name: NonEmptyString
    provider: str
    attributes: Secret[dict]


class CloudCredentialCreate(CredentialsEntry):
    id: Excluded = excluded_field()


class CloudCredentialUpdate(CloudCredentialCreate, metaclass=ForUpdateMetaclass):
    pass


class CredentialsCreateArgs(BaseModel):
    cloud_sync_credentials_create: CloudCredentialCreate


class CredentialsCreateResult(BaseModel):
    result: CredentialsEntry


class CredentialsUpdateArgs(BaseModel):
    id: int
    cloud_sync_credentials_update: CloudCredentialUpdate


class CredentialsUpdateResult(BaseModel):
    result: CredentialsEntry


class CredentialsDeleteArgs(BaseModel):
    id: int


class CredentialsDeleteResult(BaseModel):
    result: bool


@single_argument_args("cloud_sync_credentials_create")
class CredentialsVerifyArgs(BaseModel):
    provider: str
    attributes: Secret[dict]


@single_argument_result
class CredentialsVerifyResult(BaseModel):
    valid: bool
    error: LongString | None = None
    excerpt: LongString | None = None
