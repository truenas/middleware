import re
from typing import Annotated, Literal, TypeAlias

from pydantic import AfterValidator, Field, PositiveInt, Secret, StringConstraints

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, match_validator, NonEmptyString, single_argument_args,
    LongString, ForUpdateMetaclass,
)
from .pool_scrub import PoolScan


__all__ = [
    "PoolEntry", "PoolDdtPruneArgs", "PoolDdtPruneResult", "PoolDdtPrefetchArgs", "PoolDdtPrefetchResult",
    "PoolAttachArgs", "PoolAttachResult", "PoolAttachmentsArgs", "PoolAttachmentsResult", "PoolCreateArgs",
    "PoolCreateResult", "PoolDetachArgs", "PoolDetachResult", "PoolExpandArgs", "PoolExpandResult", "PoolExportArgs",
    "PoolExportResult", "PoolFilesystemChoicesArgs", "PoolFilesystemChoicesResult", "PoolGetDisksArgs",
    "PoolGetDisksResult", "PoolImportFindArgs", "PoolImportFindResult", "PoolImportPoolArgs", "PoolImportPoolResult",
    "PoolIsUpgradedArgs", "PoolIsUpgradedResult", "PoolOfflineArgs", "PoolOfflineResult", "PoolOnlineArgs",
    "PoolOnlineResult", "PoolProcessesArgs", "PoolProcessesResult", "PoolRemoveArgs", "PoolRemoveArgs",
    "PoolRemoveResult", "PoolReplaceArgs", "PoolReplaceResult", "PoolScrubArgs", "PoolScrubResult", "PoolUpdateArgs",
    "PoolUpdateResult", "PoolUpgradeArgs", "PoolUpgradeResult", "PoolValidateNameArgs", "PoolValidateNameResult",
    "PoolCreateEncryptionOptions",
]


# Incus cannot consume a pool which has whitespaces in its name.
# FIXME: Once this is fixed on incus side, we can remove this and keep on relying libzfs to do the validation only
POOL_NAME: TypeAlias = Annotated[
    NonEmptyString,
    AfterValidator(
        match_validator(
            re.compile(r"^\S+$"),
            "Pool name must not contain whitespace"
        )
    ),
    StringConstraints(max_length=50)
]


class PoolTopology(BaseModel):
    data: list
    """Array of data vdev configurations in the pool."""
    log: list
    """Array of ZFS Intent Log (ZIL) vdev configurations."""
    cache: list
    """Array of L2ARC cache vdev configurations."""
    spare: list
    """Array of spare disk configurations."""
    special: list
    """Array of special vdev configurations for metadata."""
    dedup: list
    """Array of deduplication table vdev configurations."""


class PoolEntry(BaseModel):
    id: int
    """Unique identifier for this storage pool."""
    name: str
    """Name of the storage pool."""
    guid: str
    """Globally unique identifier (GUID) for this pool."""
    status: str = Field(examples=["ONLINE", "DEGRADED", "FAULTED"])
    """Current status of the pool."""
    path: str
    """Filesystem path where the pool is mounted."""
    scan: PoolScan | None
    """Information about any active scrub or resilver operation. `null` if no operation is running."""
    expand: Annotated[
        dict,
        Field(examples=[{
            'state': 'FINISHED',
            'expanding_vdev': 0,
            'start_time': None,
            'end_time': None,
            'bytes_to_reflow': 835584,
            'bytes_reflowed': 978944,
            'waiting_for_resilver': 0,
            'total_secs_left': None,
            'percentage': 85.35564853556485,
        }])
    ] | None
    """Information about any active pool expansion operation. `null` if no expansion is running."""
    is_upgraded: bool = False
    """Whether this pool has been upgraded to the latest feature flags."""
    healthy: bool
    """Whether the pool is in a healthy state with no errors or warnings."""
    warning: bool
    """Whether the pool has warning conditions that require attention."""
    status_code: str | None
    """Detailed status code for the pool condition. `null` if not applicable."""
    status_detail: str | None
    """Human-readable description of the pool status. `null` if not available."""
    size: int | None
    """Total size of the pool in bytes. `null` if not available."""
    allocated: int | None
    """Amount of space currently allocated in the pool in bytes. `null` if not available."""
    free: int | None
    """Amount of free space available in the pool in bytes. `null` if not available."""
    freeing: int | None
    """Amount of space being freed (in bytes) by ongoing operations. `null` if not available."""
    dedup_table_size: int | None
    """Size of the deduplication table in bytes. `null` if deduplication is not enabled."""
    dedup_table_quota: str | None
    """Quota limit for the deduplication table. `null` if no quota is set."""
    fragmentation: str | None
    """Percentage of pool fragmentation as a string. `null` if not available."""
    size_str: str | None
    """Human-readable string representation of the pool size. `null` if not available."""
    allocated_str: str | None
    """Human-readable string representation of allocated space. `null` if not available."""
    free_str: str | None
    """Human-readable string representation of free space. `null` if not available."""
    freeing_str: str | None
    """Human-readable string representation of space being freed. `null` if not available."""
    autotrim: dict = Field(examples=[{
        'parsed': 'off',
        'rawvalue': 'off',
        'source': 'DEFAULT',
        'value': 'off',
    }])
    """Auto-trim configuration for the pool indicating whether automatic TRIM operations are enabled."""
    topology: PoolTopology | None
    """Physical topology and structure of the pool including vdevs. `null` if not available."""


class PoolAttach(BaseModel):
    target_vdev: str
    """GUID or device name of the target vdev to attach to."""
    new_disk: str
    """Name of the new disk to attach."""
    allow_duplicate_serials: bool = False
    """Whether to allow attaching disks with duplicate serial numbers."""


class PoolAttachment(BaseModel):
    type: str
    """Type of attachment."""
    service: str | None
    """Name of the service using this pool. `null` if not a service attachment."""
    attachments: list[str]
    """Array of specific attachment identifiers or paths."""


class PoolCreateEncryptionOptions(BaseModel):
    """Encryption options for pool creation. Keys are stored by the system for automatic locking/unlocking on \
    import/export of encrypted datasets. If that is not desired, datasets should be created with a passphrase as a \
    key."""
    generate_key: bool = False
    """Automatically generate the key to be used for dataset encryption."""
    pbkdf2iters: int = Field(ge=100000, default=350000)
    """Number of PBKDF2 iterations for key derivation from passphrase. Higher iterations improve security \
    against brute force attacks but increase unlock time. Default 350,000 balances security and performance."""
    algorithm: Literal[
        "AES-128-CCM", "AES-192-CCM", "AES-256-CCM", "AES-128-GCM", "AES-192-GCM", "AES-256-GCM"
    ] = "AES-256-GCM"
    """Encryption algorithm to use for dataset encryption."""
    passphrase: Secret[Annotated[str, Field(min_length=8)] | None] = None
    """Must be specified if encryption for root dataset is desired with a passphrase as a key."""
    key: Secret[Annotated[str, Field(min_length=64, max_length=64)] | None] = None
    """A hex-encoded key specified as an alternative to using `passphrase`."""


class PoolCreateTopologyVdevDRAID(BaseModel):
    type: Literal["DRAID1", "DRAID2", "DRAID3"]
    """Type of distributed RAID configuration."""
    disks: list[str]
    """Array of disk names to use in this DRAID vdev."""
    draid_data_disks: int | None = None
    """Defaults to `zfs.VDEV_DRAID_MAX_CHILDREN`."""
    draid_spare_disks: int = 0
    """Number of distributed spare disks in the DRAID configuration."""


class PoolCreateTopologyVdevNonDRAID(BaseModel):
    type: Literal["RAIDZ1", "RAIDZ2", "RAIDZ3", "MIRROR", "STRIPE"]
    """Type of vdev configuration."""
    disks: list[str]
    """Array of disk names to use in this vdev."""


PoolCreateTopologyDataVdev: TypeAlias = Annotated[
    PoolCreateTopologyVdevDRAID | PoolCreateTopologyVdevNonDRAID,
    Field(discriminator="type")
]


PoolCreateTopologySpecialVdev: TypeAlias = PoolCreateTopologyDataVdev


class PoolCreateTopologyDedupVdev(BaseModel):
    type: Literal["MIRROR", "STRIPE"]
    """Type of deduplication table vdev configuration."""
    disks: list[str]
    """Array of disk names to use in this dedup vdev."""


class PoolCreateTopologyCacheVdev(BaseModel):
    type: Literal["STRIPE"]
    """Type of L2ARC cache vdev configuration (always stripe)."""
    disks: list[str]
    """Array of disk names to use in this cache vdev."""


class PoolCreateTopologyLogVdev(BaseModel):
    type: Literal["MIRROR", "STRIPE"]
    """Type of ZFS Intent Log (ZIL) vdev configuration."""
    disks: list[str]
    """Array of disk names to use in this log vdev."""


class PoolCreateTopology(BaseModel):
    data: list[PoolCreateTopologyDataVdev] = Field(min_length=1)
    """All vdevs must be of the same `type`."""
    special: list[PoolCreateTopologySpecialVdev] = []
    """Array of special vdev configurations for metadata storage."""
    dedup: list[PoolCreateTopologyDedupVdev] = []
    """Array of deduplication table vdev configurations."""
    cache: list[PoolCreateTopologyCacheVdev] = []
    """Array of L2ARC cache vdev configurations."""
    log: list[PoolCreateTopologyLogVdev] = []
    """Array of ZFS Intent Log (ZIL) vdev configurations."""
    spares: list[str] = []
    """Array of spare disk names for the pool."""


class PoolCreate(BaseModel):
    name: POOL_NAME
    """Name for the new storage pool."""
    encryption: bool = False
    """If set, create a ZFS encrypted root dataset for this pool."""
    dedup_table_quota: Literal["AUTO", "CUSTOM", None] = "AUTO"
    """How to manage the deduplication table quota allocation."""
    dedup_table_quota_value: PositiveInt | None = None
    """Custom quota value in bytes when `dedup_table_quota` is set to CUSTOM."""
    deduplication: Literal["ON", "VERIFY", "OFF", None] = None
    """Make sure no block of data is duplicated in the pool. If set to `VERIFY` and two blocks have similar \
    signatures, byte-to-byte comparison is performed to ensure that the blcoks are identical. This should be used in \
    special circumstances as it carries a significant overhead."""
    checksum: Literal[
        "ON", "OFF", "FLETCHER2", "FLETCHER4", "SHA256", "SHA512", "SKEIN", "EDONR", "BLAKE3", None
    ] = None
    """Checksum algorithm to use for data integrity verification."""
    encryption_options: PoolCreateEncryptionOptions = Field(default_factory=PoolCreateEncryptionOptions)
    """Specify configuration for encryption of root dataset."""
    topology: PoolCreateTopology = Field(examples=[{
        "data": [{
            "type": "RAIDZ1",
            "disks": ["da1", "da2", "da3"]
        }],
        "cache": [{
            "type": "STRIPE",
            "disks": ["da4"]
        }],
        "log": [{
            "type": "STRIPE",
            "disks": ["da5"]
        }],
        "spares": ["da6"]
    }])
    """Physical layout and configuration of vdevs in the pool."""
    allow_duplicate_serials: bool = False
    """Whether to allow disks with duplicate serial numbers in the pool."""


class PoolDetachOptions(BaseModel):
    label: str
    """GUID or device name of the vdev to detach."""
    wipe: bool = False
    """Whether to wipe the detached disk after removal."""


class PoolExport(BaseModel):
    cascade: bool = False
    """Delete all attachments of the given pool (`pool.attachments`)."""
    restart_services: bool = False
    """Restart services that have open files on given pool."""
    destroy: bool = False
    """PERMANENTLY destroy the pool/data."""


class PoolImportFind(BaseModel):
    name: str
    """Name of the pool available for import."""
    guid: str
    """GUID of the pool available for import."""
    status: str
    """Current status of the importable pool."""
    hostname: str
    """Hostname where the pool was last mounted."""


class PoolLabel(BaseModel):
    label: str
    """The vdev guid or device name."""


class PoolProcess(BaseModel):
    pid: int
    """Process ID of the process using the pool."""
    name: str
    """Name of the process using the pool."""
    service: str | None
    """Name of the service if this process belongs to a system service."""
    cmdline: LongString | None
    """Full command line of the process."""


class PoolReplace(BaseModel):
    label: str
    """GUID or device name of the disk to replace."""
    disk: str
    """Name of the new disk to use as replacement."""
    force: bool = False
    """Force the replacement even if the new disk appears to be in use."""
    preserve_settings: bool = True
    """Whether to preserve disk settings from the replaced disk."""
    preserve_description: bool = True
    """Whether to preserve the description from the replaced disk."""


class PoolUpdateTopology(PoolCreateTopology, metaclass=ForUpdateMetaclass):
    """Cannot change type of existing vdevs."""
    data: list[PoolCreateTopologyDataVdev]


class PoolUpdate(PoolCreate, metaclass=ForUpdateMetaclass):
    autotrim: Literal["ON", "OFF"]
    """Whether to enable automatic TRIM operations on the pool."""
    name: Excluded = excluded_field()
    encryption: Excluded = excluded_field()
    encryption_options: Excluded = excluded_field()
    deduplication: Excluded = excluded_field()
    checksum: Excluded = excluded_field()
    topology: PoolUpdateTopology
    """Updated topology configuration for adding new vdevs to the pool."""


# -----------------   Args and Results   -------------------- #


@single_argument_args("options")
class PoolDdtPruneArgs(BaseModel):
    pool_name: NonEmptyString
    """Name of the pool to prune deduplication table entries from."""
    percentage: Annotated[int, Field(ge=1, le=100)] | None = None
    """Percentage of deduplication table entries to prune."""
    days: Annotated[int, Field(ge=1)] | None = None
    """Remove entries older than this many days."""


class PoolDdtPruneResult(BaseModel):
    result: None
    """Returns `null` on successful deduplication table pruning."""


class PoolDdtPrefetchArgs(BaseModel):
    pool_name: NonEmptyString
    """Name of the pool to prefetch deduplication table entries for."""


class PoolDdtPrefetchResult(BaseModel):
    result: None
    """Returns `null` on successful deduplication table prefetch."""


class PoolAttachArgs(BaseModel):
    oid: int
    """ID of the pool to attach a disk to."""
    options: PoolAttach
    """Configuration for the disk attachment operation."""


class PoolAttachResult(BaseModel):
    result: None
    """Returns `null` on successful disk attachment."""


class PoolAttachmentsArgs(BaseModel):
    id: int
    """ID of the pool to retrieve attachments for."""


class PoolAttachmentsResult(BaseModel):
    result: list[PoolAttachment]
    """Array of services and resources using this pool."""


class PoolCreateArgs(BaseModel):
    data: PoolCreate
    """Configuration for creating a new storage pool."""


class PoolCreateResult(BaseModel):
    result: PoolEntry
    """Information about the newly created pool."""


class PoolDetachArgs(BaseModel):
    id: int
    """ID of the pool to detach a disk from."""
    options: PoolDetachOptions
    """Configuration for the disk detachment operation."""


class PoolDetachResult(BaseModel):
    result: Literal[True]
    """Indicates successful disk detachment."""


class PoolExpandArgs(BaseModel):
    id: int
    """ID of the pool to expand."""


class PoolExpandResult(BaseModel):
    result: None
    """Returns `null` on successful pool expansion initiation."""


class PoolExportArgs(BaseModel):
    id: int
    """ID of the pool to export."""
    options: PoolExport = Field(default_factory=PoolExport)
    """Options for controlling the pool export process."""


class PoolExportResult(BaseModel):
    result: None
    """Returns `null` on successful pool export."""


class PoolFilesystemChoicesArgs(BaseModel):
    types: list[Literal["FILESYSTEM", "VOLUME"]] = ["FILESYSTEM", "VOLUME"]
    """Dataset types to include in the results."""


class PoolFilesystemChoicesResult(BaseModel):
    result: list[str]
    """Array of available filesystem/dataset paths."""


class PoolGetDisksArgs(BaseModel):
    id: int | None = None
    """ID of the pool to get disks for. If `null`, returns disks from all pools."""


class PoolGetDisksResult(BaseModel):
    result: list[str]
    """Array of disk device names used in the specified pool(s)."""


class PoolImportFindArgs(BaseModel):
    pass


class PoolImportFindResult(BaseModel):
    result: list[PoolImportFind]
    """Pools available for import."""


@single_argument_args("pool_import")
class PoolImportPoolArgs(BaseModel):
    guid: str
    """GUID of the pool to import."""
    name: POOL_NAME | None = None
    """If specified, import the pool using this name."""


class PoolImportPoolResult(BaseModel):
    result: Literal[True]
    """Indicates successful pool import."""


class PoolIsUpgradedArgs(BaseModel):
    id: int
    """ID of the pool to check upgrade status for."""


class PoolIsUpgradedResult(BaseModel):
    result: bool
    """Whether the pool has been upgraded to the latest feature flags."""


class PoolOfflineArgs(BaseModel):
    id: int
    """ID of the pool to modify."""
    options: PoolLabel
    """Disk identifier to take offline."""


class PoolOfflineResult(BaseModel):
    result: Literal[True]


class PoolOnlineArgs(BaseModel):
    id: int
    """ID of the pool to bring a disk online in."""
    options: PoolLabel
    """Disk identifier to bring online."""


class PoolOnlineResult(BaseModel):
    result: Literal[True]
    """Indicates successful disk online operation."""


class PoolProcessesArgs(BaseModel):
    id: int
    """ID of the pool to get processes for."""


class PoolProcessesResult(BaseModel):
    result: list[PoolProcess]
    """Array of processes currently using the pool."""


class PoolRemoveArgs(BaseModel):
    id: int
    """ID of the pool to remove a disk from."""
    options: PoolLabel
    """Disk identifier to remove from the pool."""


class PoolRemoveResult(BaseModel):
    result: None
    """Returns `null` on successful disk removal."""


class PoolReplaceArgs(BaseModel):
    id: int
    """ID of the pool to replace a disk in."""
    options: PoolReplace
    """Configuration for the disk replacement operation."""


class PoolReplaceResult(BaseModel):
    result: Literal[True]
    """Indicates successful disk replacement initiation."""


class PoolScrubArgs(BaseModel):
    id: int
    """ID of the pool to perform scrub action on."""
    action: Literal["START", "STOP", "PAUSE"]
    """The scrub action to perform."""


class PoolScrubResult(BaseModel):
    result: None
    """Returns `null` on successful scrub action."""


class PoolUpdateArgs(BaseModel):
    id: int
    """ID of the pool to update."""
    data: PoolUpdate
    """Updated configuration for the pool."""


class PoolUpdateResult(BaseModel):
    result: PoolEntry
    """The updated pool configuration."""


class PoolUpgradeArgs(BaseModel):
    id: int
    """ID of the pool to upgrade to the latest feature flags."""


class PoolUpgradeResult(BaseModel):
    result: Literal[True]
    """Indicates successful pool upgrade."""


class PoolValidateNameArgs(BaseModel):
    pool_name: POOL_NAME
    """Pool name to validate for compliance with naming rules."""


class PoolValidateNameResult(BaseModel):
    result: Literal[True]
    """Indicates the pool name is valid."""
