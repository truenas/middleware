from pydantic import Secret

from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString,
                                  single_argument_args, single_argument_result)

__all__ = ["CloudCredentialEntry",
           "CloudCredentialCreateArgs", "CloudCredentialCreateResult",
           "CloudCredentialUpdateArgs", "CloudCredentialUpdateResult",
           "CloudCredentialDeleteArgs", "CloudCredentialDeleteResult",
           "CloudCredentialVerifyArgs", "CloudCredentialVerifyResult"]


class CloudCredentialEntry(BaseModel):
    id: int
    name: NonEmptyString
    provider: str
    attributes: Secret[dict]


class CloudCredentialCreate(CloudCredentialEntry):
    id: Excluded = excluded_field()


class CloudCredentialUpdate(CloudCredentialCreate, metaclass=ForUpdateMetaclass):
    pass


class CloudCredentialCreateArgs(BaseModel):
    cloud_sync_credentials_create: CloudCredentialCreate


class CloudCredentialCreateResult(BaseModel):
    result: CloudCredentialEntry


class CloudCredentialUpdateArgs(BaseModel):
    id: int
    cloud_sync_credentials_update: CloudCredentialUpdate


class CloudCredentialUpdateResult(BaseModel):
    result: CloudCredentialEntry


class CloudCredentialDeleteArgs(BaseModel):
    id: int


class CloudCredentialDeleteResult(BaseModel):
    result: bool


@single_argument_args("cloud_sync_credentials_create")
class CloudCredentialVerifyArgs(BaseModel):
    provider: str
    attributes: Secret[dict]


@single_argument_result
class CloudCredentialVerifyResult(BaseModel):
    valid: bool
    error: str | None = None
    excerpt: str | None = None
