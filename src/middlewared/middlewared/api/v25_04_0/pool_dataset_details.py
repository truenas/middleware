from middlewared.api.base import BaseModel

from pydantic import Field


class ZFSValues(BaseModel):
    value: str | None
    rawvalue: str
    parsed: str | int | None
    source: str
    source_info: str | None


class NFSEntry(BaseModel):
    enabled: bool
    path: str


class SMBEntry(BaseModel):
    enabled: bool
    path: str
    share_name: str


class ISCSIEntry(BaseModel):
    enabled: bool
    path: str
    type_: str = Field(alias="type")


class VMEntry(BaseModel):
    name: str
    path: str


class VirtEntry(BaseModel):
    name: str
    path: str


class AppEntry(BaseModel):
    name: str
    path: str


class PoolDatasetDetailsModel(BaseModel):
    id: str
    type_: str = Field(alias="type")
    name: str
    pool: str
    encrypted: bool
    encryption_root: str | None
    key_loaded: bool
    mountpoint: str
    snapshot_count: int
    locked: bool
    atime: bool
    casesensitive: bool
    readonly: bool
    thick_provisioned: bool
    nfs_shares: list[NFSEntry]
    smb_shares: list[SMBEntry]
    iscsi_shares: list[ISCSIEntry]
    vms: list[VMEntry]
    apps: list[AppEntry]
    virt_instances: list[VirtEntry]
    replication_tasks_count: int
    snapshot_tasks_count: int
    cloudsync_tasks_count: int
    rsync_tasks_count: int
    deduplication: ZFSValues
    sync: ZFSValues
    compression: ZFSValues
    origin: ZFSValues
    quota: ZFSValues
    refquota: ZFSValues
    reservation: ZFSValues
    refreservation: ZFSValues
    key_format: ZFSValues
    encryption_algorithm: ZFSValues
    used: ZFSValues
    usedbychildren: ZFSValues
    usedbydataset: ZFSValues
    usedbysnapshots: ZFSValues
    available: ZFSValues


class PoolDatasetDetailsEntry(PoolDatasetDetailsModel):
    children: list[PoolDatasetDetailsModel]


class PoolDatasetDetailsArgs(BaseModel):
    pass


class PoolDatasetDetailsResults(BaseModel):
    result: PoolDatasetDetailsEntry
