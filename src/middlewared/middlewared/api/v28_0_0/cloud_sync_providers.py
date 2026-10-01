import re
from typing import Annotated, Literal, Union

from pydantic import AfterValidator, Discriminator, Field, Secret

from middlewared.api.base import BaseModel, HttpsOnlyURL, HttpUrl, LongNonEmptyString, NonEmptyString, match_validator

__all__ = [
    "CloudCredentialProvider",
    "AzureBlobCredentialsModel",
    "B2CredentialsModel",
    "BoxCredentialsModel",
    "DropboxCredentialsModel",
    "FTPCredentialsModel",
    "GoogleCloudStorageCredentialsModel",
    "GoogleDriveCredentialsModel",
    "GooglePhotosCredentialsModel",
    "HTTPCredentialsModel",
    "HubicCredentialsModel",
    "MegaCredentialsModel",
    "OneDriveCredentialsModel",
    "PCloudCredentialsModel",
    "S3CredentialsModel",
    "SFTPCredentialsModel",
    "StorjIxCredentialsModel",
    "SwiftCredentialsModel",
    "WebDavCredentialsModel",
    "YandexCredentialsModel",
]


class AzureBlobCredentialsModel(BaseModel):
    type: Literal["AZUREBLOB"] = Field(description="Cloud provider type identifier for Microsoft Azure Blob storage.")
    account: Secret[Annotated[
        NonEmptyString,
        AfterValidator(
            match_validator(
                re.compile(r"^[a-z0-9\-.]+$", re.IGNORECASE),
                "Account Name field can only contain alphanumeric characters, - and .",
            )
        )
    ]] = Field(description="Azure Blob Storage account name for authentication.")
    key: Secret[NonEmptyString] = Field(description="Azure Blob Storage access key for authentication.")
    endpoint: Secret[Literal[""] | HttpUrl] = Field(
        default="",
        description="Custom Azure Blob Storage endpoint URL. Empty string for default endpoints.",
    )


class B2CredentialsModel(BaseModel):
    type: Literal["B2"] = Field(description="Cloud provider type identifier for Backblaze B2 storage.")
    account: Secret[NonEmptyString] = Field(description="Backblaze B2 account ID for authentication.")
    key: Secret[NonEmptyString] = Field(description="Backblaze B2 application key for authentication.")


class BoxCredentialsModel(BaseModel):
    type: Literal["BOX"] = Field(description="Cloud provider type identifier for Box cloud storage.")
    client_id: Secret[str] = Field(default="", description="Box OAuth application client ID.")
    client_secret: Secret[str] = Field(default="", description="Box OAuth application client secret.")
    token: Secret[LongNonEmptyString] = Field(description="Box OAuth access token for API authentication.")


class DropboxCredentialsModel(BaseModel):
    type: Literal["DROPBOX"] = Field(description="Cloud provider type identifier for Dropbox storage.")
    client_id: Secret[str] = Field(default="", description="Dropbox OAuth application client ID.")
    client_secret: Secret[str] = Field(default="", description="Dropbox OAuth application client secret.")
    token: Secret[LongNonEmptyString] = Field(description="Dropbox OAuth access token for API authentication.")


class FTPCredentialsModel(BaseModel):
    type: Literal["FTP"] = Field(description="Cloud provider type identifier for FTP.")
    host: Secret[NonEmptyString] = Field(description="FTP server hostname or IP address.")
    port: Secret[int] = Field(default=21, description="FTP server port number.")
    user: Secret[NonEmptyString] = Field(description="FTP username for authentication.")
    pass_: Secret[str] = Field(alias="pass", description="FTP password for authentication.")


class GoogleCloudStorageCredentialsModel(BaseModel):
    type: Literal["GOOGLE_CLOUD_STORAGE"] = Field(
        description="Cloud provider type identifier for Google Cloud Storage.",
    )
    service_account_credentials: Secret[LongNonEmptyString] = Field(
        description="JSON service account credentials for Google Cloud Storage authentication.",
    )


class GoogleDriveCredentialsModel(BaseModel):
    type: Literal["GOOGLE_DRIVE"] = Field(description="Cloud provider type identifier for Google Drive.")
    client_id: Secret[str] = Field(default="", description="OAuth client ID for Google Drive API access.")
    client_secret: Secret[str] = Field(default="", description="OAuth client secret for Google Drive API access.")
    token: Secret[LongNonEmptyString] = Field(description="OAuth access token for Google Drive authentication.")
    team_drive: Secret[str] = Field(
        default="",
        description="Google Drive team drive ID or empty string for personal drive.",
    )


class GooglePhotosCredentialsModel(BaseModel):
    type: Literal["GOOGLE_PHOTOS"] = Field(description="Cloud provider type identifier for Google Photos.")
    client_id: Secret[str] = Field(default="", description="OAuth client ID for Google Photos API access.")
    client_secret: Secret[str] = Field(default="", description="OAuth client secret for Google Photos API access.")
    token: Secret[LongNonEmptyString] = Field(description="OAuth access token for Google Photos authentication.")


class HTTPCredentialsModel(BaseModel):
    type: Literal["HTTP"] = Field(description="Cloud provider type identifier for HTTP.")
    url: Secret[HttpUrl] = Field(description="HTTP URL for file access.")


class HubicCredentialsModel(BaseModel):
    type: Literal["HUBIC"] = Field(description="Cloud provider type identifier for Hubic.")
    token: Secret[LongNonEmptyString] = Field(description="OAuth access token for Hubic authentication.")


class MegaCredentialsModel(BaseModel):
    type: Literal["MEGA"] = Field(description="Cloud provider type identifier for MEGA.")
    user: Secret[NonEmptyString] = Field(description="MEGA username for authentication.")
    pass_: Secret[NonEmptyString] = Field(alias="pass", description="MEGA password for authentication.")


class OneDriveCredentialsModel(BaseModel):
    type: Literal["ONEDRIVE"] = Field(description="Cloud provider type identifier for OneDrive.")
    client_id: Secret[str] = Field(default="", description="OAuth client ID for OneDrive API access.")
    client_secret: Secret[str] = Field(default="", description="OAuth client secret for OneDrive API access.")
    token: Secret[LongNonEmptyString] = Field(description="OAuth access token for OneDrive authentication.")
    drive_type: Secret[Literal["PERSONAL", "BUSINESS", "DOCUMENT_LIBRARY"]] = Field(
        description="Type of OneDrive to access.",
    )
    drive_id: Secret[str] = Field(description="OneDrive drive identifier.")


class PCloudCredentialsModel(BaseModel):
    type: Literal["PCLOUD"] = Field(description="Cloud provider type identifier for pCloud.")
    client_id: Secret[str] = Field(default="", description="OAuth client ID for pCloud API access.")
    client_secret: Secret[str] = Field(default="", description="OAuth client secret for pCloud API access.")
    token: Secret[LongNonEmptyString] = Field(description="OAuth access token for pCloud authentication.")
    hostname: Secret[str] = Field(default="", description="pCloud hostname or empty string for default.")


class S3CredentialsModel(BaseModel):
    type: Literal["S3"] = Field(description="Cloud provider type identifier for S3-compatible storage.")
    access_key_id: Secret[NonEmptyString] = Field(description="S3 access key ID for authentication.")
    secret_access_key: Secret[NonEmptyString] = Field(description="S3 secret access key for authentication.")
    endpoint: Literal[""] | HttpUrl = Field(
        default="",
        description="S3-compatible endpoint URL or empty string for AWS S3.",
    )
    region: Secret[str] = Field(default="", description="S3 region or empty string for default.")
    skip_region: Secret[bool] = Field(default=False, description="Whether to skip region validation.")
    signatures_v2: Secret[bool] = Field(default=False, description="Whether to use AWS Signature Version 2.")
    max_upload_parts: Secret[int] = Field(default=10000, description="Maximum number of parts for multipart uploads.")
    provider: str = Field(
        default="Other",
        description="S3 provider. See `cloudsync.credentials.s3_provider_choices` for possible values.",
    )
    force_path_style: bool = Field(
        default=True,
        description="If true use path style access if false use virtual hosted style.",
    )
    sign_accept_encoding: bool = Field(
        default=True,
        description=(
            "Set this to `false` if your S3 server is behind a proxy that modified HTTP headers and you are "
            "experiencing `SignatureDoesNotMatch` error."
        ),
    )


class SFTPCredentialsModel(BaseModel):
    type: Literal["SFTP"] = Field(description="Cloud provider type identifier for SFTP.")
    host: Secret[NonEmptyString] = Field(description="SFTP server hostname or IP address.")
    port: Secret[int] = Field(default=22, description="SFTP server port number.")
    user: Secret[NonEmptyString] = Field(description="SFTP username for authentication.")
    pass_: Secret[str | None] = Field(
        alias="pass",
        default=None,
        description="SFTP password for authentication or `null` for key-based auth.",
    )
    private_key: Secret[int | None] = Field(
        default=None,
        description="SSH private key ID for authentication or `null` for password auth.",
    )


class StorjIxCredentialsModel(BaseModel):
    type: Literal["STORJ_IX"] = Field(description="Cloud provider type identifier for Storj decentralized storage.")
    access_key_id: Secret[NonEmptyString] = Field(description="Storj S3-compatible access key ID for authentication.")
    secret_access_key: Secret[NonEmptyString] = Field(
        description="Storj S3-compatible secret access key for authentication.",
    )
    endpoint: HttpsOnlyURL = Field(
        default="https://gateway.storjshare.io/",
        description="Storj gateway endpoint URL for S3-compatible access.",
    )


class SwiftCredentialsModel(BaseModel):
    type: Literal["OPENSTACK_SWIFT"] = Field(description="Cloud provider type identifier for OpenStack Swift storage.")
    user: Secret[NonEmptyString] = Field(description="Swift username for authentication.")
    key: Secret[NonEmptyString] = Field(description="Swift password or API key for authentication.")
    auth: Secret[NonEmptyString] = Field(description="Swift authentication URL endpoint.")
    user_id: Secret[str] = Field(default="", description="Swift user ID for authentication.")
    domain: Secret[str] = Field(default="", description="Swift domain name for authentication.")
    tenant: Secret[str] = Field(default="", description="Swift tenant name for multi-tenancy.")
    tenant_id: Secret[str] = Field(default="", description="Swift tenant ID for multi-tenancy.")
    tenant_domain: Secret[str] = Field(default="", description="Swift tenant domain name.")
    region: Secret[str] = Field(default="", description="Swift region name for geographic distribution.")
    storage_url: Secret[str] = Field(default="", description="Swift storage URL endpoint.")
    auth_token: Secret[str] = Field(default="", description="Swift authentication token for pre-authenticated access.")
    application_credential_id: Secret[str] = Field(
        default="",
        description="Swift application credential ID for authentication.",
    )
    application_credential_name: Secret[str] = Field(
        default="",
        description="Swift application credential name for authentication.",
    )
    application_credential_secret: Secret[str] = Field(
        default="",
        description="Swift application credential secret for authentication.",
    )
    auth_version: Secret[None | Literal[0, 1, 2, 3]] = Field(
        description=(
            "Swift authentication API version.\n"
            "\n"
            "* `0`: Legacy auth\n"
            "* `1`: TempAuth\n"
            "* `2`: Keystone v2.0\n"
            "* `3`: Keystone v3\n"
            "* `null`: Auto-detect"
        ),
    )
    endpoint_type: Secret[None | Literal["public", "internal", "admin"]] = Field(
        description=(
            "Swift endpoint type to use.\n"
            "\n"
            "* `public`: Public endpoint (default)\n"
            "* `internal`: Internal network endpoint\n"
            "* `admin`: Administrative endpoint\n"
            "* `null`: Use default"
        ),
    )


class WebDavCredentialsModel(BaseModel):
    type: Literal["WEBDAV"] = Field(description="Cloud provider type identifier for WebDAV servers.")
    url: Secret[HttpUrl] = Field(description="WebDAV server URL endpoint.")
    vendor: Secret[Literal["NEXTCLOUD", "OWNCLOUD", "SHAREPOINT", "OTHER"]] = Field(
        description=(
            "WebDAV server vendor type for compatibility optimizations.\n"
            "\n"
            "* `NEXTCLOUD`: Nextcloud server\n"
            "* `OWNCLOUD`: ownCloud server\n"
            "* `SHAREPOINT`: Microsoft SharePoint\n"
            "* `OTHER`: Generic WebDAV server"
        ),
    )
    user: Secret[str] = Field(description="WebDAV username for authentication.")
    pass_: Secret[str] = Field(alias="pass", description="WebDAV password for authentication.")


class YandexCredentialsModel(BaseModel):
    type: Literal["YANDEX"] = Field(description="Cloud provider type identifier for Yandex Disk storage.")
    client_id: Secret[str] = Field(default="", description="Yandex OAuth application client ID.")
    client_secret: Secret[str] = Field(default="", description="Yandex OAuth application client secret.")
    token: Secret[LongNonEmptyString] = Field(description="Yandex OAuth access token for API authentication.")


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
        MegaCredentialsModel,
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
