from typing import Literal

from pydantic import Secret

from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongNonEmptyString,
                                  LongString, NonEmptyString, single_argument_args, single_argument_result)
from .cloud_sync_providers import CloudCredentialProvider

__all__ = ["CloudCredentialEntry",
           "CredentialsCreateArgs", "CredentialsCreateResult",
           "CredentialsUpdateArgs", "CredentialsUpdateResult",
           "CredentialsDeleteArgs", "CredentialsDeleteResult",
           "CredentialsVerifyArgs", "CredentialsVerifyResult",
           "CloudSyncOneDriveListDrivesArgs", "CloudSyncOneDriveListDrivesResult"]


class CloudCredentialEntry(BaseModel):
    id: int
    name: NonEmptyString
    provider: CloudCredentialProvider


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


class CredentialsVerifyArgs(BaseModel):
    cloud_sync_credentials_create: CloudCredentialProvider


@single_argument_result
class CredentialsVerifyResult(BaseModel):
    valid: bool
    error: LongString | None = None
    excerpt: LongString | None = None


@single_argument_args("onedrive_list_drives")
class CloudSyncOneDriveListDrivesArgs(BaseModel):
    client_id: Secret[str] = ""
    client_secret: Secret[str] = ""
    token: Secret[LongNonEmptyString]


class CloudSyncOneDriveListDrivesResult(BaseModel):
    result: list["CloudSyncOneDriveListDrivesDrive"]


class CloudSyncOneDriveListDrivesDrive(BaseModel):
    drive_id: str
    drive_type: Literal["PERSONAL", "BUSINESS", "DOCUMENT_LIBRARY"]
    name: str
    description: str
