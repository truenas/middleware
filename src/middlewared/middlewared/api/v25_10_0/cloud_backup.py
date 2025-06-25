from datetime import datetime
from typing import Literal

from pydantic import Field, PositiveInt, Secret

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString
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
    password: Secret[NonEmptyString]
    """Password for the remote repository."""
    keep_last: PositiveInt
    """How many of the most recent backup snapshots to keep after each backup."""
    transfer_setting: Literal["DEFAULT", "PERFORMANCE", "FAST_STORAGE"] = "DEFAULT"
    """
    * DEFAULT:

        * pack size given by `$RESTIC_PACK_SIZE` (default 16 MiB)
        * read concurrency given by `$RESTIC_READ_CONCURRENCY` (default 2 files)

    * PERFORMANCE:

        * pack size = 29 MiB
        * read concurrency given by `$RESTIC_READ_CONCURRENCY` (default 2 files)

    * FAST_STORAGE:

        * pack size = 58 MiB
        * read concurrency = 100 files
    """
    absolute_paths: bool = False
    """Preserve absolute paths in each backup (cannot be set when `snapshot=True`)."""
    cache_path: str | None = None
    """Cache path. If not set, performance may degrade."""


class CloudBackupCreate(CloudBackupEntry):
    id: Excluded = excluded_field()
    credentials: int
    """ID of the cloud credential to use for each backup."""
    job: Excluded = excluded_field()
    locked: Excluded = excluded_field()


class CloudBackupUpdate(CloudBackupCreate, metaclass=ForUpdateMetaclass):
    absolute_paths: Excluded = excluded_field()


class CloudBackupRestoreOptions(BaseModel):
    exclude: list[str] = []
    """Paths to exclude from a restore using `restic restore --exclude`."""
    include: list[str] = []
    """Paths to include in a restore using `restic restore --include`."""


class CloudBackupSnapshot(BaseModel):
    id: str
    hostname: str
    """Host that created the snapshot."""
    time: datetime
    """Time at which the snapshot was created."""
    paths: list[str]
    """Paths that the snapshot includes."""

    class Config:
        extra = "allow"


class CloudBackupSnapshotItem(BaseModel):
    name: str
    """Name of the item."""
    path: str
    """Item's path in the snapshot."""
    type: Literal["dir", "file"]
    """Directory or file."""
    size: int | None
    """Size of the file in bytes."""
    mtime: datetime
    """Last modified time."""

    class Config:
        extra = "allow"


class CloudBackupSyncOptions(BaseModel):
    dry_run: bool = False
    """Simulate the backup without actually writing to the remote repository."""


class CloudBackupTransferSettingChoicesArgs(BaseModel):
    pass


class CloudBackupTransferSettingChoicesResult(BaseModel):
    result: list[Literal["DEFAULT", "PERFORMANCE", "FAST_STORAGE"]]
    """All possible values for `cloud_backup.create.transfer_setting`."""


class CloudBackupCreateArgs(BaseModel):
    cloud_backup: CloudBackupCreate


class CloudBackupCreateResult(BaseModel):
    result: CloudBackupEntry
    """The new cloud backup task."""


class CloudBackupUpdateArgs(BaseModel):
    id: int
    """ID of the cloud backup task to update."""
    data: CloudBackupUpdate


class CloudBackupUpdateResult(BaseModel):
    result: CloudBackupEntry
    """The updated cloud backup task."""


class CloudBackupDeleteArgs(BaseModel):
    id: int
    """ID of the cloud backup task to delete."""


class CloudBackupDeleteResult(BaseModel):
    result: Literal[True]
    """Task successfully deleted."""


class CloudBackupRestoreArgs(BaseModel):
    id: int
    """ID of the cloud backup task."""
    snapshot_id: str = Field(pattern="^[^-]")
    """ID of the snapshot to restore."""
    subfolder: str
    """Path within the snapshot to restore."""
    destination_path: str
    """Local path to restore to."""
    options: CloudBackupRestoreOptions = CloudBackupRestoreOptions()
    """Additional restore options."""


class CloudBackupRestoreResult(BaseModel):
    result: None


class CloudBackupListSnapshotsArgs(BaseModel):
    id: int
    """The cloud backup task ID."""


class CloudBackupListSnapshotsResult(BaseModel):
    result: list[CloudBackupSnapshot]
    """All retained backup snapshots."""


class CloudBackupListSnapshotDirectoryArgs(BaseModel):
    id: int
    """The cloud backup task ID."""
    snapshot_id: str = Field(pattern="^[^-]")
    """ID of the snapshot whose contents to list."""
    path: str = Field(pattern="^[^-]")
    """Path within the snapshot to list the contents of."""


class CloudBackupListSnapshotDirectoryResult(BaseModel):
    result: list[CloudBackupSnapshotItem]
    """All files and directories at the given snapshot path."""


class CloudBackupDeleteSnapshotArgs(BaseModel):
    id: int
    """The cloud backup task ID."""
    snapshot_id: str = Field(pattern="^[^-]")
    """ID of the snapshot to delete."""


class CloudBackupDeleteSnapshotResult(BaseModel):
    result: None


class CloudBackupSyncArgs(BaseModel):
    id: int
    """The cloud backup task ID."""
    options: CloudBackupSyncOptions = Field(default_factory=CloudBackupSyncOptions)
    """Sync options."""


class CloudBackupSyncResult(BaseModel):
    result: None


class CloudBackupAbortArgs(BaseModel):
    id: int
    """ID of the cloud backup task whose backup job to abort."""


class CloudBackupAbortResult(BaseModel):
    result: bool
    """The backup was successfully aborted."""
