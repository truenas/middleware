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
    time: TimeString = Field(description="Time at which the bandwidth limit takes effect in 24-hour format.")
    bandwidth: PositiveInt | None = Field(description="Bandwidth limit in bytes per second (upload and download).")


class CloudSyncEntry(BaseCloudEntry):
    bwlimit: list[CloudSyncBwlimit] = Field(default_factory=list, description="Schedule of bandwidth limits.")
    transfers: PositiveInt | None = Field(
        default=None,
        description="Maximum number of parallel file transfers. `null` for default.",
    )

    direction: Literal["PUSH", "PULL"] = Field(
        description=(
            "Direction of the cloud sync operation.\n"
            "\n"
            "* `PUSH`: Upload local files to cloud storage\n"
            "* `PULL`: Download files from cloud storage to local storage"
        ),
    )
    transfer_mode: Literal["SYNC", "COPY", "MOVE"] = Field(
        description=(
            "How files are transferred between local and cloud storage.\n"
            "\n"
            "* `SYNC`: Synchronize directories (add new, update changed, remove deleted)\n"
            "* `COPY`: Copy files without removing any existing files\n"
            "* `MOVE`: Move files (copy then delete from source)"
        ),
    )

    encryption: bool = Field(default=False, description="Whether to encrypt files before uploading to cloud storage.")
    filename_encryption: bool = Field(
        default=False,
        description="Whether to encrypt filenames in addition to file contents.",
    )
    encryption_password: Secret[str] = Field(
        default="",
        description="Password for client-side encryption. Empty string if encryption is disabled.",
    )
    encryption_salt: Secret[str] = Field(
        default="",
        description="Salt value for encryption key derivation. Empty string if encryption is disabled.",
    )

    create_empty_src_dirs: bool = Field(
        default=False,
        description="Whether to create empty directories in the destination that exist in the source.",
    )
    follow_symlinks: bool = Field(
        default=False,
        description="Whether to follow symbolic links and sync the files they point to.",
    )


class CloudSyncCreate(CloudSyncEntry):
    id: Excluded = excluded_field()
    credentials: int = Field(description="ID of the cloud credential.")
    job: Excluded = excluded_field()
    locked: Excluded = excluded_field()


class CloudSyncCreateArgs(BaseModel):
    cloud_sync_create: CloudSyncCreate = Field(description="Cloud sync task configuration data.")


class CloudSyncCreateResult(BaseModel):
    result: CloudSyncEntry = Field(description="The created cloud sync task configuration.")


class RestoreOpts(BaseModel):
    description: str = Field(default="", description="Description for the restore operation.")
    transfer_mode: Literal["SYNC", "COPY"] = Field(description="Transfer mode for the restore operation.")
    path: NonEmptyString = Field(description="Local path where files will be restored.")


class CloudSyncRestoreArgs(BaseModel):
    id: int = Field(description="ID of the cloud sync task to restore from.")
    opts: RestoreOpts = Field(description="Restore operation configuration options.")


class CloudSyncRestoreResult(BaseModel):
    result: CloudSyncEntry = Field(description="The created restore task configuration.")


class CloudSyncUpdate(CloudSyncCreate, metaclass=ForUpdateMetaclass):
    pass


class CloudSyncUpdateArgs(BaseModel):
    id: int = Field(description="ID of the cloud sync task to update.")
    cloud_sync_update: CloudSyncUpdate = Field(description="Updated cloud sync task configuration data.")


class CloudSyncUpdateResult(BaseModel):
    result: CloudSyncEntry = Field(description="The updated cloud sync task configuration.")


class CloudSyncDeleteArgs(BaseModel):
    id: int = Field(description="ID of the cloud sync task to delete.")


class CloudSyncDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the cloud sync task is successfully deleted.")


class CloudSyncCreateBucketArgs(BaseModel):
    credentials_id: int = Field(description="ID of the cloud credential to use for bucket creation.")
    name: str = Field(description="Name for the new bucket.")


class CloudSyncCreateBucketResult(BaseModel):
    result: None = Field(description="Returns `null` when the bucket is successfully created.")


class CloudSyncListBucketsArgs(BaseModel):
    credentials_id: int = Field(description="ID of the cloud credential to use for listing buckets.")


class CloudSyncListBucketsResult(BaseModel):
    result: list[dict] = Field(description="Array of bucket information objects.")


@single_argument_args("cloud_sync_ls")
class CloudSyncListDirectoryArgs(BaseModel):
    credentials: int = Field(description="ID of the cloud credential to use for directory listing.")
    encryption: bool = Field(default=False, description="Whether files are encrypted in cloud storage.")
    filename_encryption: bool = Field(default=False, description="Whether filenames are encrypted in cloud storage.")
    encryption_password: Secret[str] = Field(default="", description="Password for decrypting files and filenames.")
    encryption_salt: Secret[str] = Field(default="", description="Salt value for encryption key derivation.")
    attributes: CloudTaskAttributes = Field(description="Cloud provider-specific attributes for the listing operation.")
    args: str = Field(default="", description="Additional arguments for the directory listing command.")


class CloudSyncListDirectoryResult(BaseModel):
    result: list[dict] = Field(description="Array of file and directory information objects.")


class CloudSyncSyncOptions(BaseModel):
    dry_run: bool = Field(default=False, description="Whether to perform a dry run without making actual changes.")


class CloudSyncSyncArgs(BaseModel):
    id: int = Field(description="ID of the cloud sync task to run.")
    cloud_sync_sync_options: CloudSyncSyncOptions = Field(
        default_factory=CloudSyncSyncOptions,
        description="Options for the sync operation.",
    )


class CloudSyncSyncResult(BaseModel):
    result: None = Field(description="Returns `null` when the sync operation is successfully started.")


class CloudSyncSyncOnetimeArgs(BaseModel):
    cloud_sync_sync_onetime: CloudSyncCreate = Field(
        description="Cloud sync task configuration for one-time execution.",
    )
    cloud_sync_sync_onetime_options: CloudSyncSyncOptions = Field(
        default_factory=CloudSyncSyncOptions,
        description="Options for the one-time sync operation.",
    )


class CloudSyncSyncOnetimeResult(BaseModel):
    result: None = Field(description="Returns `null` when the one-time sync operation is successfully started.")


class CloudSyncAbortArgs(BaseModel):
    id: int = Field(description="ID of the cloud sync task to abort.")


class CloudSyncAbortResult(BaseModel):
    result: bool = Field(description="Returns `true` if the sync operation was successfully aborted.")


class CloudSyncProvidersArgs(BaseModel):
    pass


class CloudSyncProvidersResult(BaseModel):
    result: list["CloudSyncProvider"] = Field(
        description="Array of available cloud sync providers and their configurations.",
    )


class CloudSyncProvider(BaseModel):
    name: str = Field(description="Internal name identifier for the cloud provider.")
    title: str = Field(description="Human-readable title for the cloud provider.")
    credentials_oauth: str | None = Field(description="OAuth setup URL for the provider or `null` if not OAuth-based.")
    buckets: bool = Field(description="Set to `true` if provider supports buckets.")
    bucket_title: str | None = Field(
        description="Title for bucket concept in this provider or `null` if not applicable.",
    )
    task_schema: list["CloudSyncProviderTaskSchemaItem"] = Field(description="JSON schema for task attributes.")


class CloudSyncProviderTaskSchemaItem(BaseModel):
    property: str = Field(description="Name of the schema property for task configuration.")


@single_argument_args("onedrive_list_drives")
class CloudSyncOneDriveListDrivesArgs(BaseModel):
    client_id: Secret[str] = Field(default="", description="OAuth client ID for OneDrive API access.")
    client_secret: Secret[str] = Field(default="", description="OAuth client secret for OneDrive API access.")
    token: Secret[LongNonEmptyString] = Field(description="OAuth access token for OneDrive authentication.")


class CloudSyncOneDriveListDrivesResult(BaseModel):
    result: list["CloudSyncOneDriveListDrivesDrive"] = Field(description="Array of available OneDrive drives.")


class CloudSyncOneDriveListDrivesDrive(BaseModel):
    drive_id: str = Field(description="OneDrive drive identifier.")
    drive_type: Literal["PERSONAL", "BUSINESS", "DOCUMENT_LIBRARY"] = Field(description="Type of OneDrive.")
    name: str = Field(description="Display name of the OneDrive.")
    description: str = Field(description="Description of the OneDrive.")
