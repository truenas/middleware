from datetime import datetime
from typing import Literal

from pydantic import Field, PositiveInt, Secret

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongString, NonEmptyString
from .cloud_sync import CloudCredentialEntry
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
    description: str = ""
    path: str
    credentials: int
    attributes: dict
    schedule: CloudBackupCron = CloudBackupCron()
    pre_script: LongString = ""
    post_script: LongString = ""
    snapshot: bool = False
    include: list[NonEmptyString] = []
    exclude: list[NonEmptyString] = []
    args: LongString = ""
    enabled: bool = True

    password: Secret[NonEmptyString]
    keep_last: PositiveInt
    transfer_setting: Literal["DEFAULT", "PERFORMANCE", "FAST_STORAGE"] = "DEFAULT"
    absolute_paths: bool = False


class CloudBackupEntry(CloudBackupCreate):
    id: int
    credentials: CloudCredentialEntry
    job: dict | None
    locked: bool


class CloudBackupUpdate(CloudBackupCreate, metaclass=ForUpdateMetaclass):
    absolute_paths: Excluded = excluded_field()


class CloudBackupRestoreOptions(BaseModel):
    exclude: list[str] = []
    include: list[str] = []


class CloudBackupSnapshot(BaseModel):
    id: str
    hostname: str
    time: datetime
    paths: list[str]

    class Config:
        extra = "allow"


class CloudBackupSnapshotItem(BaseModel):
    name: str
    path: str
    type: Literal["dir", "file"]
    size: int | None
    mtime: datetime

    class Config:
        extra = "allow"


class CloudBackupSyncOptions(BaseModel):
    dry_run: bool = False


###############   Args and Results   ###############


class CloudBackupTransferSettingChoicesArgs(BaseModel):
    pass


class CloudBackupTransferSettingChoicesResult(BaseModel):
    result: list[Literal["DEFAULT", "PERFORMANCE", "FAST_STORAGE"]]


class CloudBackupCreateArgs(BaseModel):
    cloud_backup: CloudBackupCreate


class CloudBackupCreateResult(BaseModel):
    result: CloudBackupEntry


class CloudBackupUpdateArgs(BaseModel):
    id_: int
    data: CloudBackupUpdate


class CloudBackupUpdateResult(BaseModel):
    result: CloudBackupEntry


class CloudBackupDeleteArgs(BaseModel):
    id_: int


class CloudBackupDeleteResult(BaseModel):
    result: Literal[True]


class CloudBackupRestoreArgs(BaseModel):
    id_: int
    snapshot_id: str = Field(pattern=r"^[^-]")
    subfolder: str
    destination_path: str
    options: CloudBackupRestoreOptions


class CloudBackupRestoreResult(BaseModel):
    result: None


class CloudBackupListSnapshotsArgs(BaseModel):
    id_: int


class CloudBackupListSnapshotsResult(BaseModel):
    result: list[CloudBackupSnapshot]


class CloudBackupListSnapshotDirectoryArgs(BaseModel):
    id_: int
    snapshot_id: str = Field(pattern=r"^[^-]")
    path: str = Field(pattern=r"^[^-]")


class CloudBackupListSnapshotDirectoryResult(BaseModel):
    result: list[CloudBackupSnapshotItem]


class CloudBackupDeleteSnapshotArgs(BaseModel):
    id_: int
    snapshot_id: str = Field(pattern=r"^[^-]")


class CloudBackupDeleteSnapshotResult(BaseModel):
    result: None


class CloudBackupSyncArgs(BaseModel):
    id_: int
    options: CloudBackupSyncOptions = Field(default_factory=CloudBackupSyncOptions)


class CloudBackupSyncResult(BaseModel):
    result: None


class CloudBackupAbortArgs(BaseModel):
    id_: int


class CloudBackupAbortResult(BaseModel):
    result: bool
