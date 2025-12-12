import re
from typing import Annotated, Literal, Union

from pydantic import AfterValidator, Discriminator, Field, Secret

from middlewared.api.base import BaseModel, HttpUrl, LongNonEmptyString, match_validator, NonEmptyString

__all__ = ["CloudCredentialProvider"]


class AzureBlobCredentialsModel(BaseModel):
    type: Literal["AZUREBLOB"]
    account: Secret[Annotated[
        NonEmptyString,
        AfterValidator(
            match_validator(
                re.compile(r"^[a-z0-9\-.]+$", re.IGNORECASE),
                "Account Name field can only contain alphanumeric characters, - and .",
            )
        )
    ]]
    key: Secret[NonEmptyString]
    endpoint: Secret[Literal[""] | HttpUrl] = ""


class B2CredentialsModel(BaseModel):
    type: Literal["B2"]
    account: Secret[NonEmptyString]
    key: Secret[NonEmptyString]


class BoxCredentialsModel(BaseModel):
    type: Literal["BOX"]
    client_id: Secret[str] = ""
    client_secret: Secret[str] = ""
    token: Secret[LongNonEmptyString]


class DropboxCredentialsModel(BaseModel):
    type: Literal["DROPBOX"]
    client_id: Secret[str] = ""
    client_secret: Secret[str] = ""
    token: Secret[LongNonEmptyString]


class FTPCredentialsModel(BaseModel):
    type: Literal["FTP"]
    host: Secret[NonEmptyString]
    port: Secret[int] = 21
    user: Secret[NonEmptyString]
    pass_: Secret[str] = Field(alias="pass")


class GoogleCloudStorageCredentialsModel(BaseModel):
    type: Literal["GOOGLE_CLOUD_STORAGE"]
    service_account_credentials: Secret[LongNonEmptyString]


class GoogleDriveCredentialsModel(BaseModel):
    type: Literal["GOOGLE_DRIVE"]
    client_id: Secret[str] = ""
    client_secret: Secret[str] = ""
    token: Secret[LongNonEmptyString]
    team_drive: Secret[str] = ""


class GooglePhotosCredentialsModel(BaseModel):
    type: Literal["GOOGLE_PHOTOS"]
    client_id: Secret[str] = ""
    client_secret: Secret[str] = ""
    token: Secret[LongNonEmptyString]


class HTTPCredentialsModel(BaseModel):
    type: Literal["HTTP"]
    url: Secret[HttpUrl]


class HubicCredentialsModel(BaseModel):
    type: Literal["HUBIC"]
    token: Secret[LongNonEmptyString]


class OneDriveCredentialsModel(BaseModel):
    type: Literal["ONEDRIVE"]
    client_id: Secret[str] = ""
    client_secret: Secret[str] = ""
    token: Secret[LongNonEmptyString]
    drive_type: Secret[Literal["PERSONAL", "BUSINESS", "DOCUMENT_LIBRARY"]]
    drive_id: Secret[str]


class PCloudCredentialsModel(BaseModel):
    type: Literal["PCLOUD"]
    client_id: Secret[str] = ""
    client_secret: Secret[str] = ""
    token: Secret[LongNonEmptyString]
    hostname: Secret[str] = ""


class S3CredentialsModel(BaseModel):
    type: Literal["S3"]
    access_key_id: Secret[NonEmptyString]
    secret_access_key: Secret[NonEmptyString]
    endpoint: Literal[""] | HttpUrl = ""
    region: Secret[str] = ""
    skip_region: Secret[bool] = False
    signatures_v2: Secret[bool] = False
    max_upload_parts: Secret[int] = 10000


class SFTPCredentialsModel(BaseModel):
    type: Literal["SFTP"]
    host: Secret[NonEmptyString]
    port: Secret[int] = 22
    user: Secret[NonEmptyString]
    pass_: Secret[str | None] = Field(alias="pass", default=None)
    private_key: Secret[int | None] = None


class StorjIxCredentialsModel(BaseModel):
    type: Literal["STORJ_IX"]
    access_key_id: Secret[NonEmptyString]
    secret_access_key: Secret[NonEmptyString]


class SwiftCredentialsModel(BaseModel):
    type: Literal["OPENSTACK_SWIFT"]
    user: Secret[NonEmptyString]
    key: Secret[NonEmptyString]
    auth: Secret[NonEmptyString]
    user_id: Secret[str] = ""
    domain: Secret[str] = ""
    tenant: Secret[str] = ""
    tenant_id: Secret[str] = ""
    tenant_domain: Secret[str] = ""
    region: Secret[str] = ""
    storage_url: Secret[str] = ""
    auth_token: Secret[str] = ""
    application_credential_id: Secret[str] = ""
    application_credential_name: Secret[str] = ""
    application_credential_secret: Secret[str] = ""
    auth_version: Secret[None | Literal[0, 1, 2, 3]]
    endpoint_type: Secret[None | Literal["public", "internal", "admin"]]


class WebDavCredentialsModel(BaseModel):
    type: Literal["WEBDAV"]
    url: Secret[HttpUrl]
    vendor: Secret[Literal["NEXTCLOUD", "OWNCLOUD", "SHAREPOINT", "OTHER"]]
    user: Secret[str]
    pass_: Secret[str] = Field(alias="pass")


class YandexCredentialsModel(BaseModel):
    type: Literal["YANDEX"]
    client_id: Secret[str] = ""
    client_secret: Secret[str] = ""
    token: Secret[LongNonEmptyString]


CloudCredentialProvider = Annotated[
    Union[
        AzureBlobCredentialsModel,
        B2CredentialsModel,
        BoxCredentialsModel,
        DropboxCredentialsModel,
        FTPCredentialsModel,
        GoogleCloudStorageCredentialsModel,
        GoogleDriveCredentialsModel,
        GooglePhotosCredentialsModel,
        HTTPCredentialsModel,
        HubicCredentialsModel,
        OneDriveCredentialsModel,
        PCloudCredentialsModel,
        S3CredentialsModel,
        SFTPCredentialsModel,
        StorjIxCredentialsModel,
        SwiftCredentialsModel,
        WebDavCredentialsModel,
        YandexCredentialsModel,
    ],
    Discriminator("type"),
]
