from typing import Optional

from middlewared.api.base import *

__all__ = ["CloudCredentialEntry",
           "CloudCredentialCreateArgs", "CloudCredentialCreateResult",
           "CloudCredentialUpdateArgs", "CloudCredentialUpdateResult",
           "CloudCredentialDeleteArgs", "CloudCredentialDeleteResult",
           "CloudCredentialVerifyArgs", "CloudCredentialVerifyResult"]


class CloudCredentialEntry(BaseModel):
    id: int
    name: NonEmptyString
    provider: str
    attributes: Private[dict]


class CloudCredentialCreate(CloudCredentialEntry):
    id: excluded() = excluded_field()


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


class CloudCredentialVerifyArgs(BaseModel):
    provider: str
    attributes: Private[dict]


class CloudCredentialVerifyResult(BaseModel):
    valid: bool
    error: Optional[str] = None
    excerpt: Optional[str] = None
