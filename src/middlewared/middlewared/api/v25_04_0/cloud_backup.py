from datetime import datetime
from typing import Literal

from pydantic import Field, PositiveInt, Secret

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongString, NonEmptyString
from .cloud_sync import CredentialsEntry
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


class CloudBackupCreate(BaseModel):
    description: str = Field(default="", description="The name of the task to display in the UI")
    path: str = Field(description="The local path to back up beginning with `/mnt` or `/dev/zvol`")
    credentials: int = Field(description="ID of the cloud credential to use for each backup")
    attributes: dict = Field(description="Additional information for each backup, e.g. bucket name")
    schedule: CloudBackupCron = Field(
        default=CloudBackupCron(),
        description="Cron schedule dictating when the task should run",
    )
    pre_script: LongString = Field(default="", description="A Bash script to run immediately before every backup")
    post_script: LongString = Field(
        default="",
        description="A Bash script to run immediately after every backup if it succeeds",
    )
    snapshot: bool = Field(
        default=False,
        description="Whether to create a temporary snapshot of the dataset before every backup",
    )
    include: list[NonEmptyString] = Field(default=[], description="Paths to pass to `restic backup --include`")
    exclude: list[NonEmptyString] = Field(default=[], description="Paths to pass to `restic backup --exclude`")
    args: LongString = Field(default="", description="(Slated for removal)")
    enabled: bool = Field(default=True, description="Can enable/disable the task")

    password: Secret[NonEmptyString] = Field(description="Password for the remote repository")
    keep_last: PositiveInt = Field(description="How many of the most recent backup snapshots to keep after each backup")
    transfer_setting: Literal["DEFAULT", "PERFORMANCE", "FAST_STORAGE"] = Field(
        default="DEFAULT",
        description=(
            "DEFAULT:\n"
            "- pack size given by `$RESTIC_PACK_SIZE` (default 16 MiB)\n"
            "- read concurrency given by `$RESTIC_READ_CONCURRENCY` (default 2 files)\n"
            "PERFORMANCE:\n"
            "- pack size = 29 MiB\n"
            "- read concurrency given by `$RESTIC_READ_CONCURRENCY` (default 2 files)\n"
            "FAST_STORAGE:\n"
            "- pack size = 58 MiB\n"
            "- read concurrency = 100 files"
        ),
    )
    absolute_paths: bool = Field(
        default=False,
        description="Whether to preserve absolute paths in each backup (cannot be set when `snapshot=True`)",
    )


class CloudBackupEntry(CloudBackupCreate):
    id: int
    credentials: CredentialsEntry = Field(description="Cloud credentials to use for each backup")
    job: dict | None = Field(description="Information regarding the task's job state, e.g. progress")
    locked: bool = Field(description="A locked task cannot run")


class CloudBackupUpdate(CloudBackupCreate, metaclass=ForUpdateMetaclass):
    absolute_paths: Excluded = excluded_field()


class CloudBackupRestoreOptions(BaseModel):
    exclude: list[str] = Field(
        default=[],
        description="Paths to exclude from a restore using `restic restore --exclude`",
    )
    include: list[str] = Field(default=[], description="Paths to include in a restore using `restic restore --include`")


class CloudBackupSnapshot(BaseModel):
    id: str
    hostname: str = Field(description="Host that created the snapshot")
    time: datetime = Field(description="Time that the snapshot was created")
    paths: list[str] = Field(description="Paths that the snapshot includes")

    class Config:
        extra = "allow"


class CloudBackupSnapshotItem(BaseModel):
    name: str = Field(description="Name of the item")
    path: str = Field(description="Item's path in the snapshot")
    type: Literal["dir", "file"] = Field(description="Directory or file")
    size: int | None = Field(description="Size of the file in bytes")
    mtime: datetime = Field(description="Last modified time")

    class Config:
        extra = "allow"


class CloudBackupSyncOptions(BaseModel):
    dry_run: bool = Field(
        default=False,
        description="Whether to simulate the backup without actually writing to the remote repository",
    )


class CloudBackupTransferSettingChoicesArgs(BaseModel):
    pass


class CloudBackupTransferSettingChoicesResult(BaseModel):
    result: list[Literal["DEFAULT", "PERFORMANCE", "FAST_STORAGE"]] = Field(
        description="All possible values for `cloud_backup.create.transfer_setting`",
    )


class CloudBackupCreateArgs(BaseModel):
    cloud_backup: CloudBackupCreate


class CloudBackupCreateResult(BaseModel):
    result: CloudBackupEntry = Field(description="The new cloud backup task")


class CloudBackupUpdateArgs(BaseModel):
    id: int = Field(description="ID of the cloud backup task to update")
    data: CloudBackupUpdate


class CloudBackupUpdateResult(BaseModel):
    result: CloudBackupEntry = Field(description="The updated cloud backup task")


class CloudBackupDeleteArgs(BaseModel):
    id: int = Field(description="ID of the cloud backup task to delete")


class CloudBackupDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Task successfully deleted")


class CloudBackupRestoreArgs(BaseModel):
    id: int = Field(description="ID of the cloud backup task")
    snapshot_id: str = Field(pattern=r"^[^-]", description="ID of the snapshot to restore")
    subfolder: str = Field(description="Path within the snapshot to restore")
    destination_path: str = Field(description="Local path to restore to")
    options: CloudBackupRestoreOptions = Field(
        default=CloudBackupRestoreOptions(),
        description="Additional restore options",
    )


class CloudBackupRestoreResult(BaseModel):
    result: None


class CloudBackupListSnapshotsArgs(BaseModel):
    id: int = Field(description="The cloud backup task ID")


class CloudBackupListSnapshotsResult(BaseModel):
    result: list[CloudBackupSnapshot] = Field(description="All retained backup snapshots")


class CloudBackupListSnapshotDirectoryArgs(BaseModel):
    id: int = Field(description="The cloud backup task ID")
    snapshot_id: str = Field(pattern=r"^[^-]", description="ID of the snapshot whose contents to list")
    path: str = Field(pattern=r"^[^-]", description="Path within the snapshot to list the contents of")


class CloudBackupListSnapshotDirectoryResult(BaseModel):
    result: list[CloudBackupSnapshotItem] = Field(description="All files and directories at the given snapshot path")


class CloudBackupDeleteSnapshotArgs(BaseModel):
    id: int = Field(description="The cloud backup task ID")
    snapshot_id: str = Field(pattern=r"^[^-]", description="ID of the snapshot to delete")


class CloudBackupDeleteSnapshotResult(BaseModel):
    result: None


class CloudBackupSyncArgs(BaseModel):
    id: int = Field(description="The cloud backup task ID")
    options: CloudBackupSyncOptions = Field(default_factory=CloudBackupSyncOptions, description="Sync options")


class CloudBackupSyncResult(BaseModel):
    result: None


class CloudBackupAbortArgs(BaseModel):
    id: int = Field(description="ID of the cloud backup task whose backup job to abort")


class CloudBackupAbortResult(BaseModel):
    result: bool = Field(description="Whether the backup was successfully aborted")
