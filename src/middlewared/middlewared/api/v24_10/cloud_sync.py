from pydantic import Secret

from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongString, NonEmptyString,
                                  single_argument_args, single_argument_result)

__all__ = ["CloudCredentialEntry",
           "CredentialsCreateArgs", "CredentialsCreateResult",
           "CredentialsUpdateArgs", "CredentialsUpdateResult",
           "CredentialsDeleteArgs", "CredentialsDeleteResult",
           "CredentialsVerifyArgs", "CredentialsVerifyResult"]


class CloudCredentialEntry(BaseModel):
    id: int
    name: NonEmptyString
    provider: str
    attributes: Secret[dict]


class CloudCredentialCreate(CloudCredentialEntry):
    id: Excluded = excluded_field()


class CloudCredentialUpdate(CloudCredentialCreate, metaclass=ForUpdateMetaclass):
    pass


class CredentialsCreateArgs(BaseModel):
    cloud_sync_credentials_create: CloudCredentialCreate


class CredentialsCreateResult(BaseModel):
    result: CloudCredentialEntry


class CredentialsUpdateArgs(BaseModel):
    id: int
    cloud_sync_credentials_update: CloudCredentialUpdate


class CredentialsUpdateResult(BaseModel):
    result: CloudCredentialEntry


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
