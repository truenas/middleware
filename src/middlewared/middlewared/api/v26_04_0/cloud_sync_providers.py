import re
from typing import Annotated, Literal, Union

from pydantic import AfterValidator, Discriminator, Field, Secret

from middlewared.api.base import BaseModel, HttpUrl, LongNonEmptyString, match_validator, NonEmptyString, HttpsOnlyURL

__all__ = ["CloudCredentialProvider"]


class AzureBlobCredentialsModel(BaseModel):
    type: Literal["AZUREBLOB"]
    """Cloud provider type identifier for Microsoft Azure Blob storage."""
    account: Secret[Annotated[
        NonEmptyString,
        AfterValidator(
            match_validator(
                re.compile(r"^[a-z0-9\-.]+$", re.IGNORECASE),
                "Account Name field can only contain alphanumeric characters, - and .",
            )
        )
    ]]
    """Azure Blob Storage account name for authentication."""
    key: Secret[NonEmptyString]
    """Azure Blob Storage access key for authentication."""
    endpoint: Secret[Literal[""] | HttpUrl] = ""
    """Custom Azure Blob Storage endpoint URL. Empty string for default endpoints."""


class B2CredentialsModel(BaseModel):
    type: Literal["B2"]
    """Cloud provider type identifier for Backblaze B2 storage."""
    account: Secret[NonEmptyString]
    """Backblaze B2 account ID for authentication."""
    key: Secret[NonEmptyString]
    """Backblaze B2 application key for authentication."""


class BoxCredentialsModel(BaseModel):
    type: Literal["BOX"]
    """Cloud provider type identifier for Box cloud storage."""
    client_id: Secret[str] = ""
    """Box OAuth application client ID."""
    client_secret: Secret[str] = ""
    """Box OAuth application client secret."""
    token: Secret[LongNonEmptyString]
    """Box OAuth access token for API authentication."""


class DropboxCredentialsModel(BaseModel):
    type: Literal["DROPBOX"]
    """Cloud provider type identifier for Dropbox storage."""
    client_id: Secret[str] = ""
    """Dropbox OAuth application client ID."""
    client_secret: Secret[str] = ""
    """Dropbox OAuth application client secret."""
    token: Secret[LongNonEmptyString]
    """Dropbox OAuth access token for API authentication."""


class FTPCredentialsModel(BaseModel):
    type: Literal["FTP"]
    """Cloud provider type identifier for FTP."""
    host: Secret[NonEmptyString]
    """FTP server hostname or IP address."""
    port: Secret[int] = 21
    """FTP server port number."""
    user: Secret[NonEmptyString]
    """FTP username for authentication."""
    pass_: Secret[str] = Field(alias="pass")
    """FTP password for authentication."""


class GoogleCloudStorageCredentialsModel(BaseModel):
    type: Literal["GOOGLE_CLOUD_STORAGE"]
    """Cloud provider type identifier for Google Cloud Storage."""
    service_account_credentials: Secret[LongNonEmptyString]
    """JSON service account credentials for Google Cloud Storage authentication."""


class GoogleDriveCredentialsModel(BaseModel):
    type: Literal["GOOGLE_DRIVE"]
    """Cloud provider type identifier for Google Drive."""
    client_id: Secret[str] = ""
    """OAuth client ID for Google Drive API access."""
    client_secret: Secret[str] = ""
    """OAuth client secret for Google Drive API access."""
    token: Secret[LongNonEmptyString]
    """OAuth access token for Google Drive authentication."""
    team_drive: Secret[str] = ""
    """Google Drive team drive ID or empty string for personal drive."""


class GooglePhotosCredentialsModel(BaseModel):
    type: Literal["GOOGLE_PHOTOS"]
    """Cloud provider type identifier for Google Photos."""
    client_id: Secret[str] = ""
    """OAuth client ID for Google Photos API access."""
    client_secret: Secret[str] = ""
    """OAuth client secret for Google Photos API access."""
    token: Secret[LongNonEmptyString]
    """OAuth access token for Google Photos authentication."""


class HTTPCredentialsModel(BaseModel):
    type: Literal["HTTP"]
    """Cloud provider type identifier for HTTP."""
    url: Secret[HttpUrl]
    """HTTP URL for file access."""


class HubicCredentialsModel(BaseModel):
    type: Literal["HUBIC"]
    """Cloud provider type identifier for Hubic."""
    token: Secret[LongNonEmptyString]
    """OAuth access token for Hubic authentication."""


class MegaCredentialsModel(BaseModel):
    type: Literal["MEGA"]
    """Cloud provider type identifier for MEGA."""
    user: Secret[NonEmptyString]
    """MEGA username for authentication."""
    pass_: Secret[NonEmptyString] = Field(alias="pass")
    """MEGA password for authentication."""


class OneDriveCredentialsModel(BaseModel):
    type: Literal["ONEDRIVE"]
    """Cloud provider type identifier for OneDrive."""
    client_id: Secret[str] = ""
    """OAuth client ID for OneDrive API access."""
    client_secret: Secret[str] = ""
    """OAuth client secret for OneDrive API access."""
    token: Secret[LongNonEmptyString]
    """OAuth access token for OneDrive authentication."""
    drive_type: Secret[Literal["PERSONAL", "BUSINESS", "DOCUMENT_LIBRARY"]]
    """Type of OneDrive to access."""
    drive_id: Secret[str]
    """OneDrive drive identifier."""


class PCloudCredentialsModel(BaseModel):
    type: Literal["PCLOUD"]
    """Cloud provider type identifier for pCloud."""
    client_id: Secret[str] = ""
    """OAuth client ID for pCloud API access."""
    client_secret: Secret[str] = ""
    """OAuth client secret for pCloud API access."""
    token: Secret[LongNonEmptyString]
    """OAuth access token for pCloud authentication."""
    hostname: Secret[str] = ""
    """pCloud hostname or empty string for default."""


class S3CredentialsModel(BaseModel):
    type: Literal["S3"]
    """Cloud provider type identifier for S3-compatible storage."""
    access_key_id: Secret[NonEmptyString]
    """S3 access key ID for authentication."""
    secret_access_key: Secret[NonEmptyString]
    """S3 secret access key for authentication."""
    endpoint: str = ""
    """S3-compatible endpoint URL or empty string for AWS S3."""
    region: Secret[str] = ""
    """S3 region or empty string for default."""
    skip_region: Secret[bool] = False
    """Whether to skip region validation."""
    signatures_v2: Secret[bool] = False
    """Whether to use AWS Signature Version 2."""
    max_upload_parts: Secret[int] = 10000
    """Maximum number of parts for multipart uploads."""
    provider: str = "Other"
    """S3 provider. See `cloudsync.credentials.s3_provider_choices` for possible values."""
    force_path_style: bool = True
    """If true use path style access if false use virtual hosted style."""


class SFTPCredentialsModel(BaseModel):
    type: Literal["SFTP"]
    """Cloud provider type identifier for SFTP."""
    host: Secret[NonEmptyString]
    """SFTP server hostname or IP address."""
    port: Secret[int] = 22
    """SFTP server port number."""
    user: Secret[NonEmptyString]
    """SFTP username for authentication."""
    pass_: Secret[str | None] = Field(alias="pass", default=None)
    """SFTP password for authentication or `null` for key-based auth."""
    private_key: Secret[int | None] = None
    """SSH private key ID for authentication or `null` for password auth."""


class StorjIxCredentialsModel(BaseModel):
    type: Literal["STORJ_IX"]
    """Cloud provider type identifier for Storj decentralized storage."""
    access_key_id: Secret[NonEmptyString]
    """Storj S3-compatible access key ID for authentication."""
    secret_access_key: Secret[NonEmptyString]
    """Storj S3-compatible secret access key for authentication."""
    endpoint: HttpsOnlyURL = "https://gateway.storjshare.io/"
    """Storj gateway endpoint URL for S3-compatible access."""


class SwiftCredentialsModel(BaseModel):
    type: Literal["OPENSTACK_SWIFT"]
    """Cloud provider type identifier for OpenStack Swift storage."""
    user: Secret[NonEmptyString]
    """Swift username for authentication."""
    key: Secret[NonEmptyString]
    """Swift password or API key for authentication."""
    auth: Secret[NonEmptyString]
    """Swift authentication URL endpoint."""
    user_id: Secret[str] = ""
    """Swift user ID for authentication."""
    domain: Secret[str] = ""
    """Swift domain name for authentication."""
    tenant: Secret[str] = ""
    """Swift tenant name for multi-tenancy."""
    tenant_id: Secret[str] = ""
    """Swift tenant ID for multi-tenancy."""
    tenant_domain: Secret[str] = ""
    """Swift tenant domain name."""
    region: Secret[str] = ""
    """Swift region name for geographic distribution."""
    storage_url: Secret[str] = ""
    """Swift storage URL endpoint."""
    auth_token: Secret[str] = ""
    """Swift authentication token for pre-authenticated access."""
    application_credential_id: Secret[str] = ""
    """Swift application credential ID for authentication."""
    application_credential_name: Secret[str] = ""
    """Swift application credential name for authentication."""
    application_credential_secret: Secret[str] = ""
    """Swift application credential secret for authentication."""
    auth_version: Secret[None | Literal[0, 1, 2, 3]]
    """Swift authentication API version.

    * `0`: Legacy auth
    * `1`: TempAuth
    * `2`: Keystone v2.0
    * `3`: Keystone v3
    * `null`: Auto-detect
    """
    endpoint_type: Secret[None | Literal["public", "internal", "admin"]]
    """Swift endpoint type to use.

    * `public`: Public endpoint (default)
    * `internal`: Internal network endpoint
    * `admin`: Administrative endpoint
    * `null`: Use default
    """


class WebDavCredentialsModel(BaseModel):
    type: Literal["WEBDAV"]
    """Cloud provider type identifier for WebDAV servers."""
    url: Secret[HttpUrl]
    """WebDAV server URL endpoint."""
    vendor: Secret[Literal["NEXTCLOUD", "OWNCLOUD", "SHAREPOINT", "OTHER"]]
    """WebDAV server vendor type for compatibility optimizations.

    * `NEXTCLOUD`: Nextcloud server
    * `OWNCLOUD`: ownCloud server
    * `SHAREPOINT`: Microsoft SharePoint
    * `OTHER`: Generic WebDAV server
    """
    user: Secret[str]
    """WebDAV username for authentication."""
    pass_: Secret[str] = Field(alias="pass")
    """WebDAV password for authentication."""


class YandexCredentialsModel(BaseModel):
    type: Literal["YANDEX"]
    """Cloud provider type identifier for Yandex Disk storage."""
    client_id: Secret[str] = ""
    """Yandex OAuth application client ID."""
    client_secret: Secret[str] = ""
    """Yandex OAuth application client secret."""
    token: Secret[LongNonEmptyString]
    """Yandex OAuth access token for API authentication."""


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
