from middlewared.api.base import BaseModel

# from pydantic import ConfigDict, Field

__all__ = ("PoolDatasetDetailsArgs", "PoolDatasetDetailsResult")

"""
FIXME: We need to fix the return validation
for this model but it is involved and tricky
and requires a ton of testing. (i.e. you need
to have a system with smb/nfs/iscsi/apps/vm/virt
shares created AND zpools with zfs dataset and zvols.)
class ZFSValues(BaseModel):
    value: str | None
    rawvalue: str
    parsed: str | int | None
    source: str
    source_info: str | None


class PDD_NFSEntry(BaseModel):
    enabled: bool
    path: str


class PDD_SMBEntry(BaseModel):
    enabled: bool
    path: str
    share_name: str


class PDD_ISCSIEntry(BaseModel):
    enabled: bool
    path: str
    type_: str = Field(alias="type")


class PDD_VMEntry(BaseModel):
    name: str
    path: str


class PDD_VirtEntry(BaseModel):
    name: str
    path: str


class PDD_AppEntry(BaseModel):
    name: str
    path: str


class PoolDatasetDetailsModel(BaseModel):
    model_config = ConfigDict(extra="allow")
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
    nfs_shares: list[PDD_NFSEntry]
    smb_shares: list[PDD_SMBEntry]
    iscsi_shares: list[PDD_ISCSIEntry]
    vms: list[PDD_VMEntry]
    apps: list[PDD_AppEntry]
    virt_instances: list[PDD_VirtEntry]
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
    model_config = ConfigDict(extra="allow")
    children: list[PoolDatasetDetailsModel]


class PoolDatasetDetailsArgs(BaseModel):
    pass


class PoolDatasetDetailsResult(BaseModel):
    result: list[PoolDatasetDetailsEntry]
"""


class PoolDatasetDetailsArgs(BaseModel):
    pass


class PoolDatasetDetailsResult(BaseModel):
    result: list[dict]
