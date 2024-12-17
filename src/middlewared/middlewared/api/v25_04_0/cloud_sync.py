# TODO: rename to cloudsync_credentials.py
from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString,
                                  single_argument_result)
from .cloud_sync_providers import CloudCredentialProvider

__all__ = ["CloudCredentialEntry",
           "CloudCredentialCreateArgs", "CloudCredentialCreateResult",
           "CloudCredentialUpdateArgs", "CloudCredentialUpdateResult",
           "CloudCredentialDeleteArgs", "CloudCredentialDeleteResult",
           "CloudCredentialVerifyArgs", "CloudCredentialVerifyResult"]


class CloudCredentialEntry(BaseModel):
    id: int
    name: NonEmptyString
    provider: CloudCredentialProvider

    @classmethod
    def from_previous(cls, value):
        attributes = value.pop("attributes")
        return {
            **value,
            "provider": {
                "type": value["provider"],
                **attributes,
            }
        }

    @classmethod
    def to_previous(cls, value):
        value["attributes"] = value["provider"]
        value["provider"] = value["attributes"].pop("type")
        return value


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


class CloudCredentialVerifyArgs(BaseModel):
    cloud_sync_credentials_create: CloudCredentialProvider

    @classmethod
    def from_previous(cls, value):
        return {
            "cloud_sync_credentials_create": {
                "type": value["cloud_sync_credentials_create"]["provider"],
                **value["cloud_sync_credentials_create"]["attributes"]
            }
        }


@single_argument_result
class CloudCredentialVerifyResult(BaseModel):
    valid: bool
    error: str | None = None
    excerpt: str | None = None
