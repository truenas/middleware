from typing import Annotated, Literal

from pydantic import Field, PositiveInt, Secret

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, NonEmptyString, single_argument_args, NotRequired, LongString
)


__all__ = [
    "PoolEntry", "DDTPruneArgs", "DDTPruneResult", "DDTPrefetchArgs", "DDTPrefetchResult", "PoolAttachArgs",
    "PoolAttachResult", "PoolAttachmentsArgs", "PoolAttachmentsResult", "PoolCreateArgs", "PoolCreateResult",
    "PoolDetachArgs", "PoolDetachResult", "PoolExpandArgs", "PoolExpandResult", "PoolExportArgs", "PoolExportResult",
    "PoolFilesystemChoicesArgs", "PoolFilesystemChoicesResult", "PoolGetDisksArgs", "PoolGetDisksResult",
    "PoolImportFindArgs", "PoolImportFindResult", "PoolImportPoolArgs", "PoolImportPoolResult", "PoolIsUpgradedArgs",
    "PoolIsUpgradedResult", "PoolOfflineArgs", "PoolOfflineResult", "PoolOnlineArgs", "PoolOnlineResult",
    "PoolProcessesArgs", "PoolProcessesResult", "PoolRemoveArgs", "PoolRemoveArgs", "PoolRemoveResult",
    "PoolReplaceArgs", "PoolReplaceResult", "PoolScrubArgs", "PoolScrubResult", "PoolUpdateArgs", "PoolUpdateResult",
    "PoolUpgradeArgs", "PoolUpgradeResult", "PoolValidateNameArgs", "PoolValidateNameResult",
    "PoolCreateEncryptionOptions",
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
    """
    example={
        'function': None,
        'state': None,
        'start_time': None,
        'end_time': None,
        'percentage': None,
        'bytes_to_process': None,
        'bytes_processed': None,
        'bytes_issued': None,
        'pause': None,
        'errors': None,
        'total_secs_left': None,
    }
    """
    expand: dict | None
    """
    example={
        'state': 'FINISHED',
        'expanding_vdev': 0,
        'start_time': None,
        'end_time': None,
        'bytes_to_reflow': 835584,
        'bytes_reflowed': 978944,
        'waiting_for_resilver': 0,
        'total_secs_left': None,
        'percentage': 85.35564853556485,
    }
    """
    is_upgraded: bool = False
    healthy: bool
    warning: bool
    status_code: str | None
    status_detail: str | None
    size: int | None
    allocated: int | None
    free: int | None
    freeing: int | None
    dedup_table_size: int | None
    dedup_table_quota: str | None
    fragmentation: str | None
    size_str: str | None
    allocated_str: str | None
    free_str: str | None
    freeing_str: str | None
    autotrim: dict
    """
    example={
        'parsed': 'off',
        'rawvalue': 'off',
        'source': 'DEFAULT',
        'value': 'off',
    }
    """
    topology: PoolTopology | None


class PoolAttach(BaseModel):
    target_vdev: str
    new_disk: str
    allow_duplicate_serials: bool = False


class PoolAttachment(BaseModel):
    type: str
    service: str | None
    attachments: list[str]


class PoolCreateEncryptionOptions(BaseModel):
    generate_key: bool = False
    pbkdf2iters: Annotated[int, Field(ge=100000)] = 350000
    algorithm: Literal[
        "AES-128-CCM", "AES-192-CCM", "AES-256-CCM", "AES-128-GCM", "AES-192-GCM", "AES-256-GCM"
    ] = "AES-256-GCM"
    passphrase: Secret[Annotated[str, Field(min_length=8)] | None] = None
    key: Secret[Annotated[str, Field(min_length=64, max_length=64)] | None] = None


class PoolCreateTopologyDataVdevDRAID(BaseModel):
    type: Literal["DRAID1", "DRAID2", "DRAID3"]
    disks: list[str]
    draid_data_disks: int | None = None
    """Defaults to `zfs.VDEV_DRAID_MAX_CHILDREN`."""
    draid_spare_disks: int = 0


class PoolCreateTopologyDataVdevNonDRAID(BaseModel):
    type: Literal["RAIDZ1", "RAIDZ2", "RAIDZ3", "MIRROR", "STRIPE"]
    disks: list[str]


PoolCreateTopologyDataVdev = Annotated[
    PoolCreateTopologyDataVdevDRAID | PoolCreateTopologyDataVdevNonDRAID,
    Field(discriminator="type")
]


class PoolCreateTopologySpecialVdev(BaseModel):
    type: Literal["MIRROR", "STRIPE"]
    disks: list[str]


class PoolCreateTopologyDedupVdev(BaseModel):
    type: Literal["MIRROR", "STRIPE"]
    disks: list[str]


class PoolCreateTopologyCacheVdev(BaseModel):
    type: Literal["STRIPE"]
    disks: list[str]


class PoolCreateTopologyLogVdev(BaseModel):
    type: Literal["MIRROR", "STRIPE"]
    disks: list[str]


class PoolCreateTopology(BaseModel):
    data: Annotated[list[PoolCreateTopologyDataVdev], Field(min_length=1)]
    special: list[PoolCreateTopologySpecialVdev] = NotRequired
    dedup: list[PoolCreateTopologyDedupVdev] = NotRequired
    cache: list[PoolCreateTopologyCacheVdev] = NotRequired
    log: list[PoolCreateTopologyLogVdev] = NotRequired
    spares: list[str] = NotRequired


class PoolCreate(BaseModel):
    name: Annotated[str, Field(max_length=50)]
    encryption: bool = False
    dedup_table_quota: Literal["AUTO", "CUSTOM", None] = "AUTO"
    dedup_table_quota_value: PositiveInt | None = None
    deduplication: Literal["ON", "VERIFY", "OFF", None] = None
    checksum: Literal[
        "ON", "OFF", "FLETCHER2", "FLETCHER4", "SHA256", "SHA512", "SKEIN", "EDONR", "BLAKE3", None
    ] = None
    encryption_options: PoolCreateEncryptionOptions = Field(default_factory=PoolCreateEncryptionOptions)
    topology: PoolCreateTopology
    allow_duplicate_serials: bool = False


class PoolDetachOptions(BaseModel):
    label: str
    wipe: bool = False


class PoolExport(BaseModel):
    cascade: bool = False
    """Delete all attachments of the given pool (`pool.attachments`)."""
    restart_services: bool = False
    """Restart services that have open files on given pool."""
    destroy: bool = False
    """PERMANENTLY destroy the pool/data."""


class PoolImportFind(BaseModel):
    name: str
    guid: str
    status: str
    hostname: str


class PoolLabel(BaseModel):
    label: str
    """The vdev guid or device name."""


class PoolProcess(BaseModel):
    pid: int
    name: str
    service: str = NotRequired
    cmdline: LongString = NotRequired


class PoolReplace(BaseModel):
    label: str
    disk: str
    force: bool = False
    preserve_settings: bool = True
    preserve_description: bool = True


class PoolUpdateTopology(PoolCreateTopology):
    data: Annotated[list[PoolCreateTopologyDataVdev], Field(min_length=1)] = NotRequired


class PoolUpdate(PoolCreate):
    autotrim: Literal["ON", "OFF"] = NotRequired
    name: Excluded = excluded_field()
    encryption: Excluded = excluded_field()
    encryption_options: Excluded = excluded_field()
    deduplication: Excluded = excluded_field()
    checksum: Excluded = excluded_field()
    topology: PoolUpdateTopology = {}


######################   Args and Results   ######################


@single_argument_args("options")
class DDTPruneArgs(BaseModel):
    pool_name: NonEmptyString
    percentage: Annotated[int, Field(ge=1, le=100)] | None = None
    days: Annotated[int, Field(ge=1)] | None = None


class DDTPruneResult(BaseModel):
    result: None


class DDTPrefetchArgs(BaseModel):
    pool_name: NonEmptyString


class DDTPrefetchResult(BaseModel):
    result: None


class PoolAttachArgs(BaseModel):
    oid: int
    options: PoolAttach


class PoolAttachResult(BaseModel):
    result: None


class PoolAttachmentsArgs(BaseModel):
    id: int


class PoolAttachmentsResult(BaseModel):
    result: list[PoolAttachment]


class PoolCreateArgs(BaseModel):
    data: PoolCreate


class PoolCreateResult(BaseModel):
    result: PoolEntry


class PoolDetachArgs(BaseModel):
    id: int
    options: PoolDetachOptions


class PoolDetachResult(BaseModel):
    result: Literal[True]


class PoolExpandArgs(BaseModel):
    id: int


class PoolExpandResult(BaseModel):
    result: None


class PoolExportArgs(BaseModel):
    id: int
    options: PoolExport = Field(default_factory=PoolExport)


class PoolExportResult(BaseModel):
    result: None


class PoolFilesystemChoicesArgs(BaseModel):
    types: list[Literal["FILESYSTEM", "VOLUME"]] = ["FILESYSTEM", "VOLUME"]


class PoolFilesystemChoicesResult(BaseModel):
    result: list[str]


class PoolGetDisksArgs(BaseModel):
    id: int | None = None


class PoolGetDisksResult(BaseModel):
    result: list[str]


class PoolImportFindArgs(BaseModel):
    pass


class PoolImportFindResult(BaseModel):
    result: list[PoolImportFind]
    """Pools available for import."""


@single_argument_args("pool_import")
class PoolImportPoolArgs(BaseModel):
    guid: str
    name: str | None = None
    """If specified, import the pool using this name."""


class PoolImportPoolResult(BaseModel):
    result: Literal[True]


class PoolIsUpgradedArgs(BaseModel):
    id: int


class PoolIsUpgradedResult(BaseModel):
    result: bool


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


class PoolProcessesArgs(BaseModel):
    id: int


class PoolProcessesResult(BaseModel):
    result: list[PoolProcess]


class PoolRemoveArgs(BaseModel):
    id: int
    options: PoolLabel


class PoolRemoveResult(BaseModel):
    result: None


class PoolReplaceArgs(BaseModel):
    id: int
    options: PoolReplace


class PoolReplaceResult(BaseModel):
    result: Literal[True]


class PoolScrubArgs(BaseModel):
    id: int
    action: Literal["START", "STOP", "PAUSE"]


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
