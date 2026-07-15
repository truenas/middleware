from datetime import datetime
from typing import Literal

from pydantic import Field, PositiveInt, Secret

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, NonEmptyString, excluded_field

from .cloud import BaseCloudEntry
from .common import CronModel

__all__ = [
    "CloudBackupEntry", "CloudBackupTransferSettingChoicesArgs", "CloudBackupTransferSettingChoicesResult",
    "CloudBackupCreateArgs", "CloudBackupCreateResult", "CloudBackupUpdateArgs", "CloudBackupUpdateResult",
    "CloudBackupDeleteArgs", "CloudBackupDeleteResult", "CloudBackupRestoreArgs", "CloudBackupRestoreResult",
    "CloudBackupListSnapshotsArgs", "CloudBackupListSnapshotsResult", "CloudBackupListSnapshotDirectoryArgs",
    "CloudBackupListSnapshotDirectoryResult", "CloudBackupDeleteSnapshotArgs", "CloudBackupDeleteSnapshotResult",
    "CloudBackupSyncArgs", "CloudBackupSyncResult", "CloudBackupAbortArgs", "CloudBackupAbortResult",
]


class CloudBackupCron(CronModel):
    minute: str = "00"


class CloudBackupEntry(BaseCloudEntry):
    password: Secret[NonEmptyString] = Field(description="Password for the remote repository.")
    keep_last: PositiveInt = Field(
        description="How many of the most recent backup snapshots to keep after each backup.",
    )
    transfer_setting: Literal["DEFAULT", "PERFORMANCE", "FAST_STORAGE"] = Field(
        default="DEFAULT",
        description=(
            "* DEFAULT:\n"
            "    * pack size given by `$RESTIC_PACK_SIZE` (default 16 MiB)\n"
            "    * read concurrency given by `$RESTIC_READ_CONCURRENCY` (default 2 files)\n"
            "\n"
            "* PERFORMANCE:\n"
            "    * pack size = 29 MiB\n"
            "    * read concurrency given by `$RESTIC_READ_CONCURRENCY` (default 2 files)\n"
            "\n"
            "* FAST_STORAGE:\n"
            "    * pack size = 58 MiB\n"
            "    * read concurrency = 100 files"
        ),
    )
    absolute_paths: bool = Field(
        default=False,
        description="Preserve absolute paths in each backup (cannot be set when `snapshot=True`).",
    )
    cache_path: str | None = Field(default=None, description="Cache path. If not set, performance may degrade.")
    rate_limit: PositiveInt | None = Field(
        default=None,
        description=(
            "Maximum upload/download rate in KiB/s. Passed to `restic --limit-upload` on `cloud_backup.sync` and "
            "`restic --limit-download` on `cloud_backup.restore`. `null` indicates no rate limit will be imposed.\n"
            "\n"
            "Can be overridden on a sync or restore call."
        ),
    )


class CloudBackupCreate(CloudBackupEntry):
    id: Excluded = excluded_field()
    credentials: int = Field(description="ID of the cloud credential to use for each backup.")
    job: Excluded = excluded_field()
    locked: Excluded = excluded_field()


class CloudBackupUpdate(CloudBackupCreate, metaclass=ForUpdateMetaclass):
    absolute_paths: Excluded = excluded_field()


class CloudBackupRestoreOptions(BaseModel):
    exclude: list[str] = Field(
        default=[],
        description="Paths to exclude from a restore using `restic restore --exclude`.",
    )
    include: list[str] = Field(
        default=[],
        description="Paths to include in a restore using `restic restore --include`.",
    )
    rate_limit: PositiveInt | None = Field(
        default=None,
        description=(
            "Maximum download rate in KiB/s. Passed to `restic --limit-download`.\n"
            "\n"
            "If provided, overrides the task's rate limit."
        ),
    )


class CloudBackupSnapshot(BaseModel):
    id: str = Field(description="Unique identifier for this cloud backup snapshot.")
    hostname: str = Field(description="Host that created the snapshot.")
    time: datetime = Field(description="Time at which the snapshot was created.")
    paths: list[str] = Field(description="Paths that the snapshot includes.")

    class Config:
        extra = "allow"


class CloudBackupSnapshotItem(BaseModel):
    name: str = Field(description="Name of the item.")
    path: str = Field(description="Item's path in the snapshot.")
    type: Literal["dir", "file"] = Field(description="Directory or file.")
    size: int | None = Field(description="Size of the file in bytes.")
    mtime: datetime = Field(description="Last modified time.")

    class Config:
        extra = "allow"


class CloudBackupSyncOptions(BaseModel):
    dry_run: bool = Field(
        default=False,
        description="Simulate the backup without actually writing to the remote repository.",
    )
    rate_limit: PositiveInt | None = Field(
        default=None,
        description=(
            "Maximum upload rate in KiB/s. Passed to `restic --limit-upload`.\n"
            "\n"
            "If provided, overrides the task's rate limit."
        ),
    )


class CloudBackupTransferSettingChoicesArgs(BaseModel):
    pass


class CloudBackupTransferSettingChoicesResult(BaseModel):
    result: list[Literal["DEFAULT", "PERFORMANCE", "FAST_STORAGE"]] = Field(
        description="All possible values for `cloud_backup.create.transfer_setting`.",
    )


class CloudBackupCreateArgs(BaseModel):
    cloud_backup: CloudBackupCreate = Field(description="Configuration for the new cloud backup task.")


class CloudBackupCreateResult(BaseModel):
    result: CloudBackupEntry = Field(description="The new cloud backup task.")


class CloudBackupUpdateArgs(BaseModel):
    id: int = Field(description="ID of the cloud backup task to update.")
    data: CloudBackupUpdate = Field(description="Updated configuration data for the cloud backup task.")


class CloudBackupUpdateResult(BaseModel):
    result: CloudBackupEntry = Field(description="The updated cloud backup task.")


class CloudBackupDeleteArgs(BaseModel):
    id: int = Field(description="ID of the cloud backup task to delete.")


class CloudBackupDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Task successfully deleted.")


class CloudBackupRestoreArgs(BaseModel):
    id: int = Field(description="ID of the cloud backup task.")
    snapshot_id: str = Field(pattern="^[^-]", description="ID of the snapshot to restore.")
    subfolder: str = Field(description="Path within the snapshot to restore.")
    destination_path: str = Field(description="Local path to restore to.")
    options: CloudBackupRestoreOptions = Field(
        default=CloudBackupRestoreOptions(),
        description="Additional restore options.",
    )


class CloudBackupRestoreResult(BaseModel):
    result: None


class CloudBackupListSnapshotsArgs(BaseModel):
    id: int = Field(description="The cloud backup task ID.")


class CloudBackupListSnapshotsResult(BaseModel):
    result: list[CloudBackupSnapshot] = Field(description="All retained backup snapshots.")


class CloudBackupListSnapshotDirectoryArgs(BaseModel):
    id: int = Field(description="The cloud backup task ID.")
    snapshot_id: str = Field(pattern="^[^-]", description="ID of the snapshot whose contents to list.")
    path: str = Field(pattern="^[^-]", description="Path within the snapshot to list the contents of.")


class CloudBackupListSnapshotDirectoryResult(BaseModel):
    result: list[CloudBackupSnapshotItem] = Field(description="All files and directories at the given snapshot path.")


class CloudBackupDeleteSnapshotArgs(BaseModel):
    id: int = Field(description="The cloud backup task ID.")
    snapshot_id: str = Field(pattern="^[^-]", description="ID of the snapshot to delete.")


class CloudBackupDeleteSnapshotResult(BaseModel):
    result: None


class CloudBackupSyncArgs(BaseModel):
    id: int = Field(description="The cloud backup task ID.")
    options: CloudBackupSyncOptions = Field(default_factory=CloudBackupSyncOptions, description="Sync options.")


class CloudBackupSyncResult(BaseModel):
    result: None


class CloudBackupAbortArgs(BaseModel):
    id: int = Field(description="ID of the cloud backup task whose backup job to abort.")


class CloudBackupAbortResult(BaseModel):
    result: bool = Field(description="The backup was successfully aborted.")
