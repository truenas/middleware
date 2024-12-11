from typing import Annotated, Literal

from pydantic import Field, PositiveInt, Secret

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args
)


__all__ = [
    "PoolEntry", "DDTPruneArgs", "DDTPruneResult", "DDTPrefetchArgs", "DDTPrefetchResult", "PoolCreateArgs",
    "PoolCreateResult", "PoolDetachArgs", "PoolDetachResult", "PoolExportArgs", "PoolExportResult",
    "PoolGetInstanceByNameArgs", "PoolGetInstanceByNameResult", "PoolImportFindArgs", "PoolImportFindResult",
    "PoolImportPoolArgs", "PoolImportPoolResult", "PoolOfflineArgs", "PoolOfflineResult", "PoolOnlineArgs",
    "PoolOnlineResult", "PoolPoolNormalizeInfoArgs", "PoolPoolNormalizeInfoResult", "PoolRemoveArgs", "PoolRemoveArgs",
    "PoolRemoveResult", "PoolScrubArgs", "PoolScrubResult", "PoolUpdateArgs", "PoolUpdateResult", "PoolUpgradeArgs",
    "PoolUpgradeResult", "PoolValidateNameArgs", "PoolValidateNameResult"
]


class PoolTopology(BaseModel):
    data: list
    log: list
    cache: list
    spare: list
    special: list
    dedup: list


class PoolEntry(BaseModel):
    id: int
    name: str
    guid: str
    status: str
    path: str
    scan: dict | None
    expand: dict | None
    is_upgraded: bool
    healthy: bool
    warning: bool
    status_code: str | None
    status_detail: str | None
    size: int | None
    allocated: int | None
    free: int | None
    freeing: int | None
    dedupcached: int | None
    dedup_table_size: int | None
    dedup_table_quota: str | None
    fragmentation: str | None
    size_str: str | None
    allocated_str: str | None
    free_str: str | None
    freeing_str: str | None
    autotrim: dict
    topology: PoolTopology | None


class PoolCreateEncryptionOptions(BaseModel):
    generate_key: bool = False
    pbkdf2iters: Annotated[int, Field(ge=100000)] = 350000
    algorithm: Literal[
        "AES-128-CCM", "AES-192-CCM", "AES-256-CCM", "AES-128-GCM", "AES-192-GCM", "AES-256-GCM"
    ] = "AES-256-GCM"
    passphrase: Secret[Annotated[str, Field(min_length=8)] | None] = None
    key: Secret[Annotated[str, Field(min_length=64, max_length=64)] | None] = None


class PoolCreateTopologyDatavdevs(BaseModel):
    type: Literal["DRAID1", "DRAID2", "DRAID3", "RAIDZ1", "RAIDZ2", "RAIDZ3", "MIRROR", "STRIPE"]
    disks: list[str]
    draid_data_disks: int
    draid_spare_disks: int


class PoolCreateTopologySpecialvdevs(BaseModel):
    type: Literal["MIRROR", "STRIPE"]
    disks: list[str]


class PoolCreateTopologyDedupvdevs(BaseModel):
    type: Literal["MIRROR", "STRIPE"]
    disks: list[str]


class PoolCreateTopologyCachevdevs(BaseModel):
    type: Literal["STRIPE"] = "STRIPE"
    disks: list[str]


class PoolCreateTopologyLogvdevs(BaseModel):
    type: Literal["MIRROR", "STRIPE"]
    disks: list[str]


class PoolCreateTopology(BaseModel):
    data: list[PoolCreateTopologyDatavdevs] = []
    special: list[PoolCreateTopologySpecialvdevs] = []
    dedup: list[PoolCreateTopologyDedupvdevs] = []
    cache: list[PoolCreateTopologyCachevdevs] = []
    log: list[PoolCreateTopologyLogvdevs] = []
    spares: list[str] = []


class PoolUpdateTopology(PoolCreateTopology, metaclass=ForUpdateMetaclass):
    pass


class PoolCreate(BaseModel):
    name: Annotated[str, Field(max_length=50)]
    encryption: bool = False
    dedup_table_quota: Literal["AUTO", "CUSTOM"] | None = "AUTO"
    dedup_table_quota_value: PositiveInt | None = None
    deduplication: Literal["ON", "VERIFY", "OFF"] | None = None
    checksum: Literal[
        "ON", "OFF", "FLETCHER2", "FLETCHER4", "SHA256", "SHA512", "SKEIN", "EDONR", "BLAKE3"
    ] | None = None
    encryption_options: PoolCreateEncryptionOptions = Field(default_factory=PoolCreateEncryptionOptions)
    topology: PoolCreateTopology
    allow_duplicate_serials: bool = False


class PoolUpdate(PoolCreate, metaclass=ForUpdateMetaclass):
    autotrim: Literal["ON", "OFF"]
    name: Excluded = excluded_field()
    encryption: Excluded = excluded_field()
    encryption_options: Excluded = excluded_field()
    deduplication: Excluded = excluded_field()
    checksum: Excluded = excluded_field()
    topology: PoolUpdateTopology


class PoolExport(BaseModel):
    cascade: bool = False
    restart_services: bool = False
    destroy: bool = False


class PoolImportFind(BaseModel):
    name: str
    guid: str
    status: str
    hostname: str


class PoolLabel(BaseModel):
    label: str


class PoolPoolNormalizeInfo(PoolEntry):
    id: Excluded = excluded_field()
    guid: Excluded = excluded_field()
    is_upgraded: Excluded = excluded_field()


#################   Args and Results   #################


@single_argument_args("options")
class DDTPruneArgs(BaseModel):
    pool_name: NonEmptyString
    percentage: Annotated[int | None, Field(ge=1, le=100, default=None)]
    days: Annotated[int | None, Field(ge=1, default=None)]


class DDTPruneResult(BaseModel):
    result: None


class DDTPrefetchArgs(BaseModel):
    pool_name: NonEmptyString


class DDTPrefetchResult(BaseModel):
    result: None


class PoolCreateArgs(BaseModel):
    data: PoolCreate


class PoolCreateResult(BaseModel):
    result: PoolEntry


class PoolDetachArgs(BaseModel):
    id: int
    options: PoolLabel = Field(default_factory=PoolLabel)


class PoolDetachResult(BaseModel):
    result: Literal[True]


class PoolExportArgs(BaseModel):
    id: int
    options: PoolExport = Field(default_factory=PoolExport)


class PoolExportResult(BaseModel):
    result: None


class PoolGetInstanceByNameArgs(BaseModel):
    name: str


class PoolGetInstanceByNameResult(BaseModel):
    result: PoolEntry


class PoolImportFindArgs(BaseModel):
    pass


class PoolImportFindResult(BaseModel):
    result: list[PoolImportFind]
    """Pools available for import"""


@single_argument_args("pool_import")
class PoolImportPoolArgs(BaseModel):
    guid: str
    name: str | None = None
    enable_attachments: bool = False


class PoolImportPoolResult(BaseModel):
    result: Literal[True]


class PoolOfflineArgs(BaseModel):
    id: int
    options: PoolLabel


class PoolOfflineResult(BaseModel):
    result: Literal[True]


class PoolOnlineArgs(BaseModel):
    id: int
    options: PoolLabel


class PoolOnlineResult(BaseModel):
    result: Literal[True]


class PoolPoolNormalizeInfoArgs(BaseModel):
    pool_name: str


class PoolPoolNormalizeInfoResult(BaseModel):
    result: PoolPoolNormalizeInfo


class PoolRemoveArgs(BaseModel):
    id: int
    options: PoolLabel


class PoolRemoveResult(BaseModel):
    result: None


class PoolScrubArgs(BaseModel):
    id: int
    action: Literal["START", "STOP", "PAUSE"] = "START"


class PoolScrubResult(BaseModel):
    result: None


class PoolUpdateArgs(BaseModel):
    id: int
    data: PoolUpdate


class PoolUpdateResult(BaseModel):
    result: PoolEntry


class PoolUpgradeArgs(BaseModel):
    id: int


class PoolUpgradeResult(BaseModel):
    result: Literal[True]


class PoolValidateNameArgs(BaseModel):
    pool_name: str


class PoolValidateNameResult(BaseModel):
    result: Literal[True]
