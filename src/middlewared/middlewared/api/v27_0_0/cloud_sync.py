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
    """Maximum number of parallel file transfers. `null` for default."""

    direction: Literal["PUSH", "PULL"]
    """Direction of the cloud sync operation.

    * `PUSH`: Upload local files to cloud storage
    * `PULL`: Download files from cloud storage to local storage
    """
    transfer_mode: Literal["SYNC", "COPY", "MOVE"]
    """How files are transferred between local and cloud storage.

    * `SYNC`: Synchronize directories (add new, update changed, remove deleted)
    * `COPY`: Copy files without removing any existing files
    * `MOVE`: Move files (copy then delete from source)
    """

    encryption: bool = False
    """Whether to encrypt files before uploading to cloud storage."""
    filename_encryption: bool = False
    """Whether to encrypt filenames in addition to file contents."""
    encryption_password: Secret[str] = ""
    """Password for client-side encryption. Empty string if encryption is disabled."""
    encryption_salt: Secret[str] = ""
    """Salt value for encryption key derivation. Empty string if encryption is disabled."""

    create_empty_src_dirs: bool = False
    """Whether to create empty directories in the destination that exist in the source."""
    follow_symlinks: bool = False
    """Whether to follow symbolic links and sync the files they point to."""


class CloudSyncCreate(CloudSyncEntry):
    id: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    relative_path: Excluded = excluded_field()
    credentials: int
    """ID of the cloud credential."""
    job: Excluded = excluded_field()
    locked: Excluded = excluded_field()


class CloudSyncCreateArgs(BaseModel):
    cloud_sync_create: CloudSyncCreate
    """Cloud sync task configuration data."""


class CloudSyncCreateResult(BaseModel):
    result: CloudSyncEntry
    """The created cloud sync task configuration."""


class RestoreOpts(BaseModel):
    description: str = ""
    """Description for the restore operation."""
    transfer_mode: Literal["SYNC", "COPY"]
    """Transfer mode for the restore operation."""
    path: NonEmptyString
    """Local path where files will be restored."""


class CloudSyncRestoreArgs(BaseModel):
    id: int
    """ID of the cloud sync task to restore from."""
    opts: RestoreOpts
    """Restore operation configuration options."""


class CloudSyncRestoreResult(BaseModel):
    result: CloudSyncEntry
    """The created restore task configuration."""


class CloudSyncUpdate(CloudSyncCreate, metaclass=ForUpdateMetaclass):
    pass


class CloudSyncUpdateArgs(BaseModel):
    id: int
    """ID of the cloud sync task to update."""
    cloud_sync_update: CloudSyncUpdate
    """Updated cloud sync task configuration data."""


class CloudSyncUpdateResult(BaseModel):
    result: CloudSyncEntry
    """The updated cloud sync task configuration."""


class CloudSyncDeleteArgs(BaseModel):
    id: int
    """ID of the cloud sync task to delete."""


class CloudSyncDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the cloud sync task is successfully deleted."""


class CloudSyncCreateBucketArgs(BaseModel):
    credentials_id: int
    """ID of the cloud credential to use for bucket creation."""
    name: str
    """Name for the new bucket."""


class CloudSyncCreateBucketResult(BaseModel):
    result: None
    """Returns `null` when the bucket is successfully created."""


class CloudSyncListBucketsArgs(BaseModel):
    credentials_id: int
    """ID of the cloud credential to use for listing buckets."""


class CloudSyncListBucketsResult(BaseModel):
    result: list[dict]
    """Array of bucket information objects."""


@single_argument_args("cloud_sync_ls")
class CloudSyncListDirectoryArgs(BaseModel):
    credentials: int
    """ID of the cloud credential to use for directory listing."""
    encryption: bool = False
    """Whether files are encrypted in cloud storage."""
    filename_encryption: bool = False
    """Whether filenames are encrypted in cloud storage."""
    encryption_password: Secret[str] = ""
    """Password for decrypting files and filenames."""
    encryption_salt: Secret[str] = ""
    """Salt value for encryption key derivation."""
    attributes: CloudTaskAttributes
    """Cloud provider-specific attributes for the listing operation."""
    args: str = ""
    """Additional arguments for the directory listing command."""


class CloudSyncListDirectoryResult(BaseModel):
    result: list[dict]
    """Array of file and directory information objects."""


class CloudSyncSyncOptions(BaseModel):
    dry_run: bool = False
    """Whether to perform a dry run without making actual changes."""


class CloudSyncSyncArgs(BaseModel):
    id: int
    """ID of the cloud sync task to run."""
    cloud_sync_sync_options: CloudSyncSyncOptions = Field(
        default_factory=CloudSyncSyncOptions
    )
    """Options for the sync operation."""


class CloudSyncSyncResult(BaseModel):
    result: None
    """Returns `null` when the sync operation is successfully started."""


class CloudSyncSyncOnetimeArgs(BaseModel):
    cloud_sync_sync_onetime: CloudSyncCreate
    """Cloud sync task configuration for one-time execution."""
    cloud_sync_sync_onetime_options: CloudSyncSyncOptions = Field(
        default_factory=CloudSyncSyncOptions
    )
    """Options for the one-time sync operation."""


class CloudSyncSyncOnetimeResult(BaseModel):
    result: None
    """Returns `null` when the one-time sync operation is successfully started."""


class CloudSyncAbortArgs(BaseModel):
    id: int
    """ID of the cloud sync task to abort."""


class CloudSyncAbortResult(BaseModel):
    result: bool
    """Returns `true` if the sync operation was successfully aborted."""


class CloudSyncProvidersArgs(BaseModel):
    pass


class CloudSyncProvidersResult(BaseModel):
    result: list["CloudSyncProvider"]
    """Array of available cloud sync providers and their configurations."""


class CloudSyncProvider(BaseModel):
    name: str
    """Internal name identifier for the cloud provider."""
    title: str
    """Human-readable title for the cloud provider."""
    credentials_oauth: str | None
    """OAuth setup URL for the provider or `null` if not OAuth-based."""
    buckets: bool
    """Set to `true` if provider supports buckets."""
    bucket_title: str | None
    """Title for bucket concept in this provider or `null` if not applicable."""
    task_schema: list["CloudSyncProviderTaskSchemaItem"]
    """JSON schema for task attributes."""


class CloudSyncProviderTaskSchemaItem(BaseModel):
    property: str
    """Name of the schema property for task configuration."""


@single_argument_args("onedrive_list_drives")
class CloudSyncOneDriveListDrivesArgs(BaseModel):
    client_id: Secret[str] = ""
    """OAuth client ID for OneDrive API access."""
    client_secret: Secret[str] = ""
    """OAuth client secret for OneDrive API access."""
    token: Secret[LongNonEmptyString]
    """OAuth access token for OneDrive authentication."""


class CloudSyncOneDriveListDrivesResult(BaseModel):
    result: list["CloudSyncOneDriveListDrivesDrive"]
    """Array of available OneDrive drives."""


class CloudSyncOneDriveListDrivesDrive(BaseModel):
    drive_id: str
    """OneDrive drive identifier."""
    drive_type: Literal["PERSONAL", "BUSINESS", "DOCUMENT_LIBRARY"]
    """Type of OneDrive."""
    name: str
    """Display name of the OneDrive."""
    description: str
    """Description of the OneDrive."""
