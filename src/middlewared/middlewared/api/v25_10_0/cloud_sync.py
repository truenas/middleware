from typing import Literal

from pydantic import Field, PositiveInt, Secret

from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    LongNonEmptyString,
    NonEmptyString,
    single_argument_args,
    TimeString,
)
from .cloud import BaseCloudEntry, CloudTaskAttributes

__all__ = [
    "CloudTaskAttributes",
    "CloudSyncEntry",
    "CloudSyncCreateArgs",
    "CloudSyncCreateResult",
    "CloudSyncRestoreArgs",
    "CloudSyncRestoreResult",
    "CloudSyncUpdateArgs",
    "CloudSyncUpdateResult",
    "CloudSyncDeleteArgs",
    "CloudSyncDeleteResult",
    "CloudSyncCreateBucketArgs",
    "CloudSyncCreateBucketResult",
    "CloudSyncListBucketsArgs",
    "CloudSyncListBucketsResult",
    "CloudSyncListDirectoryArgs",
    "CloudSyncListDirectoryResult",
    "CloudSyncSyncArgs",
    "CloudSyncSyncResult",
    "CloudSyncSyncOnetimeArgs",
    "CloudSyncSyncOnetimeResult",
    "CloudSyncAbortArgs",
    "CloudSyncAbortResult",
    "CloudSyncProvidersArgs",
    "CloudSyncProvidersResult",
    "CloudSyncOneDriveListDrivesArgs",
    "CloudSyncOneDriveListDrivesResult",
]


class CloudSyncBwlimit(BaseModel):
    time: TimeString
    """Time at which the bandwidth limit takes effect in 24-hour format."""
    bandwidth: PositiveInt | None
    """Bandwidth limit in bytes per second (upload and download)."""


class CloudSyncEntry(BaseCloudEntry):
    bwlimit: list[CloudSyncBwlimit] = Field(default_factory=list)
    """Schedule of bandwidth limits."""
    transfers: PositiveInt | None = None

    direction: Literal["PUSH", "PULL"]
    transfer_mode: Literal["SYNC", "COPY", "MOVE"]

    encryption: bool = False
    filename_encryption: bool = False
    encryption_password: Secret[str] = ""
    encryption_salt: Secret[str] = ""

    create_empty_src_dirs: bool = False
    follow_symlinks: bool = False


class CloudSyncCreate(CloudSyncEntry):
    id: Excluded = excluded_field()
    credentials: int
    """ID of the cloud credential."""
    job: Excluded = excluded_field()
    locked: Excluded = excluded_field()


class CloudSyncCreateArgs(BaseModel):
    cloud_sync_create: CloudSyncCreate


class CloudSyncCreateResult(BaseModel):
    result: CloudSyncEntry


class RestoreOpts(BaseModel):
    description: str = ""
    transfer_mode: Literal["SYNC", "COPY"]
    path: NonEmptyString


class CloudSyncRestoreArgs(BaseModel):
    id: int
    opts: RestoreOpts


class CloudSyncRestoreResult(BaseModel):
    result: CloudSyncEntry


class CloudSyncUpdate(CloudSyncCreate, metaclass=ForUpdateMetaclass):
    pass


class CloudSyncUpdateArgs(BaseModel):
    id: int
    cloud_sync_update: CloudSyncUpdate


class CloudSyncUpdateResult(BaseModel):
    result: CloudSyncEntry


class CloudSyncDeleteArgs(BaseModel):
    id: int


class CloudSyncDeleteResult(BaseModel):
    result: Literal[True]


class CloudSyncCreateBucketArgs(BaseModel):
    credentials_id: int
    name: str


class CloudSyncCreateBucketResult(BaseModel):
    result: None


class CloudSyncListBucketsArgs(BaseModel):
    credentials_id: int


class CloudSyncListBucketsResult(BaseModel):
    result: list[dict]


@single_argument_args("cloud_sync_ls")
class CloudSyncListDirectoryArgs(BaseModel):
    credentials: int
    encryption: bool = False
    filename_encryption: bool = False
    encryption_password: Secret[str] = ""
    encryption_salt: Secret[str] = ""
    attributes: CloudTaskAttributes
    args: str = ""


class CloudSyncListDirectoryResult(BaseModel):
    result: list[dict]


class CloudSyncSyncOptions(BaseModel):
    dry_run: bool = False


class CloudSyncSyncArgs(BaseModel):
    id: int
    cloud_sync_sync_options: CloudSyncSyncOptions = Field(
        default_factory=CloudSyncSyncOptions
    )


class CloudSyncSyncResult(BaseModel):
    result: None


class CloudSyncSyncOnetimeArgs(BaseModel):
    cloud_sync_sync_onetime: CloudSyncCreate
    cloud_sync_sync_onetime_options: CloudSyncSyncOptions = Field(
        default_factory=CloudSyncSyncOptions
    )


class CloudSyncSyncOnetimeResult(BaseModel):
    result: None


class CloudSyncAbortArgs(BaseModel):
    id: int


class CloudSyncAbortResult(BaseModel):
    result: bool


class CloudSyncProvidersArgs(BaseModel):
    pass


class CloudSyncProvidersResult(BaseModel):
    result: list["CloudSyncProvider"]


class CloudSyncProvider(BaseModel):
    name: str
    title: str
    credentials_oauth: str | None
    buckets: bool
    """Set to `true` if provider supports buckets."""
    bucket_title: str | None
    task_schema: list["CloudSyncProviderTaskSchemaItem"]
    """JSON schema for task attributes."""


class CloudSyncProviderTaskSchemaItem(BaseModel):
    property: str


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
