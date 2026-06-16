from typing import Annotated, Literal, TypeAlias

from pydantic import Discriminator, Field, PositiveInt, Secret

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, NonEmptyString, single_argument_args,
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
    "PoolOnlineResult", "PoolProcessesArgs", "PoolProcessesResult", "PoolReimportArgs", "PoolReimportResult",
    "PoolRemoveArgs", "PoolRemoveArgs", "PoolRemoveResult", "PoolReplaceArgs", "PoolReplaceResult", "PoolScrubArgs",
    "PoolScrubResult", "PoolUpdateArgs", "PoolUpdateResult", "PoolUpgradeArgs", "PoolUpgradeResult",
    "PoolValidateNameArgs", "PoolValidateNameResult", "PoolCreateEncryptionOptions", "PoolPrefetchArgs",
    "PoolPrefetchResult",
]


class PoolTopology(BaseModel):
    data: list = Field(description="Array of data vdev configurations in the pool.")
    log: list = Field(description="Array of ZFS Intent Log (ZIL) vdev configurations.")
    cache: list = Field(description="Array of L2ARC cache vdev configurations.")
    spare: list = Field(description="Array of spare disk configurations.")
    special: list = Field(description="Array of special vdev configurations for metadata.")
    dedup: list = Field(description="Array of deduplication table vdev configurations.")


class PoolEntry(BaseModel):
    id: int = Field(description="Unique identifier for this storage pool.")
    name: str = Field(description="Name of the storage pool.")
    guid: str = Field(description="Globally unique identifier (GUID) for this pool.")
    all_sed: bool | None = Field(description="Set when pool is made up of SED disks.")
    status: str = Field(examples=["ONLINE", "DEGRADED", "FAULTED"], description="Current status of the pool.")
    path: str = Field(description="Filesystem path where the pool is mounted.")
    scan: PoolScan | None = Field(
        description=(
            "Information about the most recent scrub or resilver operation. `null` if no scan data is available."
        ),
    )
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
    ] | None = Field(
        description="Information about any active pool expansion operation. `null` if no expansion is running.",
    )
    is_upgraded: bool = Field(
        default=False,
        description="Whether this pool has been upgraded to the latest feature flags.",
    )
    healthy: bool = Field(description="Whether the pool is in a healthy state with no errors or warnings.")
    warning: bool = Field(description="Whether the pool has warning conditions that require attention.")
    status_code: str | None = Field(
        description="Detailed status code for the pool condition. `null` if not applicable.",
    )
    status_detail: str | None = Field(
        description="Human-readable description of the pool status. `null` if not available.",
    )
    size: int | None = Field(description="Total size of the pool in bytes. `null` if not available.")
    allocated: int | None = Field(
        description="Amount of space currently allocated in the pool in bytes. `null` if not available.",
    )
    free: int | None = Field(
        description="Amount of free space available in the pool in bytes. `null` if not available.",
    )
    freeing: int | None = Field(
        description="Amount of space being freed (in bytes) by ongoing operations. `null` if not available.",
    )
    dedup_table_size: int | None = Field(
        description="Size of the deduplication table in bytes. `null` if deduplication is not enabled.",
    )
    dedup_table_quota: str | None = Field(
        description="Quota limit for the deduplication table. `null` if no quota is set.",
    )
    fragmentation: str | None = Field(
        description="Percentage of pool fragmentation as a string. `null` if not available.",
    )
    size_str: str | None = Field(
        description="Human-readable string representation of the pool size. `null` if not available.",
    )
    allocated_str: str | None = Field(
        description="Human-readable string representation of allocated space. `null` if not available.",
    )
    free_str: str | None = Field(
        description="Human-readable string representation of free space. `null` if not available.",
    )
    freeing_str: str | None = Field(
        description="Human-readable string representation of space being freed. `null` if not available.",
    )
    autotrim: dict = Field(examples=[{
        'parsed': 'off',
        'rawvalue': 'off',
        'source': 'DEFAULT',
        'value': 'off',
    }],
        description="Auto-trim configuration for the pool indicating whether automatic TRIM operations are enabled.")
    topology: PoolTopology | None = Field(
        description="Physical topology and structure of the pool including vdevs. `null` if not available.",
    )


class PoolAttach(BaseModel):
    target_vdev: str = Field(description="GUID or device name of the target vdev to attach to.")
    new_disk: str = Field(description="Name of the new disk to attach.")
    allow_duplicate_serials: bool = Field(
        default=False,
        description="Whether to allow attaching disks with duplicate serial numbers.",
    )


class PoolAttachment(BaseModel):
    type: str = Field(description="Type of attachment.")
    service: str | None = Field(description="Name of the service using this pool. `null` if not a service attachment.")
    attachments: list[str] = Field(description="Array of specific attachment identifiers or paths.")


class PoolCreateEncryptionOptions(BaseModel):
    """Encryption options for pool creation. Keys are stored by the system for automatic locking/unlocking on \
    import/export of encrypted datasets. If that is not desired, datasets should be created with a passphrase as a \
    key."""
    generate_key: bool = Field(
        default=False,
        description="Automatically generate the key to be used for dataset encryption.",
    )
    pbkdf2iters: int = Field(
        ge=1300000,
        default=1300000,
        description=(
            "Number of PBKDF2 iterations for key derivation from passphrase. Higher iterations improve security against"
            " brute force attacks but increase unlock time."
        ),
    )
    algorithm: Literal[
        "AES-128-CCM", "AES-192-CCM", "AES-256-CCM", "AES-128-GCM", "AES-192-GCM", "AES-256-GCM"
    ] = Field(default="AES-256-GCM", description="Encryption algorithm to use for dataset encryption.")
    passphrase: Secret[Annotated[str, Field(min_length=8)] | None] = Field(
        default=None,
        description="Must be specified if encryption for root dataset is desired with a passphrase as a key.",
    )
    key: Secret[Annotated[str, Field(min_length=64, max_length=64)] | None] = Field(
        default=None,
        description="A hex-encoded key specified as an alternative to using `passphrase`.",
    )

    @classmethod
    def from_previous(cls, value):
        value['pbkdf2iters'] = max(1300000, value['pbkdf2iters'])
        return value


class PoolCreateTopologyVdevDRAID(BaseModel):
    type: Literal["DRAID1", "DRAID2", "DRAID3"] = Field(description="Type of distributed RAID configuration.")
    disks: list[str] = Field(description="Array of disk names to use in this DRAID vdev.")
    draid_data_disks: int | None = Field(default=None, description="Defaults to `zfs.VDEV_DRAID_MAX_CHILDREN`.")
    draid_spare_disks: int = Field(
        default=0,
        description="Number of distributed spare disks in the DRAID configuration.",
    )


class PoolCreateTopologyVdevNonDRAID(BaseModel):
    type: Literal["RAIDZ1", "RAIDZ2", "RAIDZ3", "MIRROR", "STRIPE"] = Field(description="Type of vdev configuration.")
    disks: list[str] = Field(description="Array of disk names to use in this vdev.")


PoolCreateTopologyDataVdev: TypeAlias = Annotated[
    PoolCreateTopologyVdevDRAID | PoolCreateTopologyVdevNonDRAID,
    Discriminator("type")
]


PoolCreateTopologySpecialVdev: TypeAlias = PoolCreateTopologyDataVdev


class PoolCreateTopologyDedupVdev(BaseModel):
    type: Literal["MIRROR", "STRIPE"] = Field(description="Type of deduplication table vdev configuration.")
    disks: list[str] = Field(description="Array of disk names to use in this dedup vdev.")


class PoolCreateTopologyCacheVdev(BaseModel):
    type: Literal["STRIPE"] = Field(description="Type of L2ARC cache vdev configuration (always stripe).")
    disks: list[str] = Field(description="Array of disk names to use in this cache vdev.")


class PoolCreateTopologyLogVdev(BaseModel):
    type: Literal["MIRROR", "STRIPE"] = Field(description="Type of ZFS Intent Log (ZIL) vdev configuration.")
    disks: list[str] = Field(description="Array of disk names to use in this log vdev.")


class PoolCreateTopology(BaseModel):
    data: list[PoolCreateTopologyDataVdev] = Field(min_length=1, description="All vdevs must be of the same `type`.")
    special: list[PoolCreateTopologySpecialVdev] = Field(
        default=[],
        description="Array of special vdev configurations for metadata storage.",
    )
    dedup: list[PoolCreateTopologyDedupVdev] = Field(
        default=[],
        description="Array of deduplication table vdev configurations.",
    )
    cache: list[PoolCreateTopologyCacheVdev] = Field(
        default=[],
        description="Array of L2ARC cache vdev configurations.",
    )
    log: list[PoolCreateTopologyLogVdev] = Field(
        default=[],
        description="Array of ZFS Intent Log (ZIL) vdev configurations.",
    )
    spares: list[str] = Field(default=[], description="Array of spare disk names for the pool.")


class PoolCreate(BaseModel):
    name: NonEmptyString = Field(description="Name for the new storage pool.")
    encryption: bool = Field(default=False, description="If set, create a ZFS encrypted root dataset for this pool.")
    dedup_table_quota: Literal["AUTO", "CUSTOM", None] = Field(
        default="AUTO",
        description="How to manage the deduplication table quota allocation.",
    )
    dedup_table_quota_value: PositiveInt | None = Field(
        default=None,
        description="Custom quota value in bytes when `dedup_table_quota` is set to CUSTOM.",
    )
    deduplication: Literal["ON", "VERIFY", "OFF", None] = Field(
        default=None,
        description=(
            "Make sure no block of data is duplicated in the pool. If set to `VERIFY` and two blocks have similar "
            "signatures, byte-to-byte comparison is performed to ensure that the blcoks are identical. This should be "
            "used in special circumstances as it carries a significant overhead."
        ),
    )
    checksum: Literal[
        "ON", "OFF", "FLETCHER2", "FLETCHER4", "SHA256", "SHA512", "SKEIN", "EDONR", "BLAKE3", None
    ] = Field(default=None, description="Checksum algorithm to use for data integrity verification.")
    encryption_options: PoolCreateEncryptionOptions = Field(
        default_factory=PoolCreateEncryptionOptions,
        description="Specify configuration for encryption of root dataset.",
    )
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
    }],
        description="Physical layout and configuration of vdevs in the pool.")
    allow_duplicate_serials: bool = Field(
        default=False,
        description="Whether to allow disks with duplicate serial numbers in the pool.",
    )
    all_sed: bool = Field(default=False, description="When set, all disks in the pool must be SED based.")


class PoolDetachOptions(BaseModel):
    label: str = Field(description="GUID or device name of the vdev to detach.")
    wipe: bool = Field(default=False, description="Whether to wipe the detached disk after removal.")


class PoolExport(BaseModel):
    cascade: bool = Field(default=False, description="Delete all attachments of the given pool (`pool.attachments`).")
    restart_services: bool = Field(default=False, description="Restart services that have open files on given pool.")
    destroy: bool = Field(default=False, description="PERMANENTLY destroy the pool/data.")


class PoolImportFind(BaseModel):
    name: str = Field(description="Name of the pool available for import.")
    guid: str = Field(description="GUID of the pool available for import.")
    status: str = Field(description="Current status of the importable pool.")
    hostname: str = Field(description="Hostname where the pool was last mounted.")


class PoolLabel(BaseModel):
    label: str = Field(description="The vdev guid or device name.")


class PoolProcess(BaseModel):
    pid: int = Field(description="Process ID of the process using the pool.")
    name: str = Field(description="Name of the process using the pool.")
    service: str | None = Field(description="Name of the service if this process belongs to a system service.")
    cmdline: LongString | None = Field(description="Full command line of the process.")


class PoolReplace(BaseModel):
    label: str = Field(description="GUID or device name of the disk to replace.")
    disk: str = Field(description="Name of the new disk to use as replacement.")
    force: bool = Field(default=False, description="Force the replacement even if the new disk appears to be in use.")
    preserve_settings: bool = Field(
        default=True,
        description="Whether to preserve disk settings from the replaced disk.",
    )
    preserve_description: bool = Field(
        default=True,
        description="Whether to preserve the description from the replaced disk.",
    )


class PoolUpdateTopology(PoolCreateTopology, metaclass=ForUpdateMetaclass):
    """Cannot change type of existing vdevs."""
    data: list[PoolCreateTopologyDataVdev]


class PoolUpdate(PoolCreate, metaclass=ForUpdateMetaclass):
    autotrim: Literal["ON", "OFF"] = Field(description="Whether to enable automatic TRIM operations on the pool.")
    name: Excluded = excluded_field()
    encryption: Excluded = excluded_field()
    encryption_options: Excluded = excluded_field()
    deduplication: Excluded = excluded_field()
    checksum: Excluded = excluded_field()
    topology: PoolUpdateTopology = Field(description="Updated topology configuration for adding new vdevs to the pool.")


# -----------------   Args and Results   -------------------- #


@single_argument_args("options")
class PoolDdtPruneArgs(BaseModel):
    pool_name: NonEmptyString = Field(description="Name of the pool to prune deduplication table entries from.")
    percentage: Annotated[int, Field(ge=1, le=100)] | None = Field(
        default=None,
        description="Percentage of deduplication table entries to prune.",
    )
    days: Annotated[int, Field(ge=1)] | None = Field(
        default=None,
        description="Remove entries older than this many days.",
    )


class PoolDdtPruneResult(BaseModel):
    result: None = Field(description="Returns `null` on successful deduplication table pruning.")


class PoolDdtPrefetchArgs(BaseModel):
    pool_name: NonEmptyString = Field(description="Name of the pool to prefetch deduplication table entries for.")


class PoolDdtPrefetchResult(BaseModel):
    result: None = Field(description="Returns `null` on successful deduplication table prefetch.")


class PoolPrefetchArgs(BaseModel):
    pool_name: NonEmptyString = Field(description="Name of the pool to prefetch metadata for.")


class PoolPrefetchResult(BaseModel):
    result: None = Field(description="Returns `null` on successful metadata prefetch.")


class PoolAttachArgs(BaseModel):
    oid: int = Field(description="ID of the pool to attach a disk to.")
    options: PoolAttach = Field(description="Configuration for the disk attachment operation.")


class PoolAttachResult(BaseModel):
    result: None = Field(description="Returns `null` on successful disk attachment.")


class PoolAttachmentsArgs(BaseModel):
    id: int = Field(description="ID of the pool to retrieve attachments for.")


class PoolAttachmentsResult(BaseModel):
    result: list[PoolAttachment] = Field(description="Array of services and resources using this pool.")


class PoolCreateArgs(BaseModel):
    data: PoolCreate = Field(description="Configuration for creating a new storage pool.")


class PoolCreateResult(BaseModel):
    result: PoolEntry = Field(description="Information about the newly created pool.")


class PoolDetachArgs(BaseModel):
    id: int = Field(description="ID of the pool to detach a disk from.")
    options: PoolDetachOptions = Field(description="Configuration for the disk detachment operation.")


class PoolDetachResult(BaseModel):
    result: Literal[True] = Field(description="Indicates successful disk detachment.")


class PoolExpandArgs(BaseModel):
    id: int = Field(description="ID of the pool to expand.")


class PoolExpandResult(BaseModel):
    result: None = Field(description="Returns `null` on successful pool expansion initiation.")


class PoolExportArgs(BaseModel):
    id: int = Field(description="ID of the pool to export.")
    options: PoolExport = Field(
        default_factory=PoolExport,
        description="Options for controlling the pool export process.",
    )


class PoolExportResult(BaseModel):
    result: None = Field(description="Returns `null` on successful pool export.")


class PoolFilesystemChoicesArgs(BaseModel):
    types: list[Literal["FILESYSTEM", "VOLUME"]] = Field(
        default=["FILESYSTEM", "VOLUME"],
        description="Dataset types to include in the results.",
    )


class PoolFilesystemChoicesResult(BaseModel):
    result: list[str] = Field(description="Array of available filesystem/dataset paths.")


class PoolGetDisksArgs(BaseModel):
    id: int | None = Field(
        default=None,
        description="ID of the pool to get disks for. If `null`, returns disks from all pools.",
    )


class PoolGetDisksResult(BaseModel):
    result: list[str] = Field(description="Array of disk device names used in the specified pool(s).")


class PoolImportFindArgs(BaseModel):
    pass


class PoolImportFindResult(BaseModel):
    result: list[PoolImportFind] = Field(description="Pools available for import.")


@single_argument_args("pool_import")
class PoolImportPoolArgs(BaseModel):
    guid: str = Field(description="GUID of the pool to import.")
    name: NonEmptyString | None = Field(default=None, description="If specified, import the pool using this name.")


class PoolImportPoolResult(BaseModel):
    result: Literal[True] = Field(description="Indicates successful pool import.")


class PoolReimportArgs(BaseModel):
    id: int = Field(description="ID of the pool to reimport.")


class PoolReimportResult(BaseModel):
    result: Literal[True] = Field(description="Indicates successful pool reimport.")


class PoolIsUpgradedArgs(BaseModel):
    id: int = Field(description="ID of the pool to check upgrade status for.")


class PoolIsUpgradedResult(BaseModel):
    result: bool = Field(description="Whether the pool has been upgraded to the latest feature flags.")


class PoolOfflineArgs(BaseModel):
    id: int = Field(description="ID of the pool to modify.")
    options: PoolLabel = Field(description="Disk identifier to take offline.")


class PoolOfflineResult(BaseModel):
    result: Literal[True]


class PoolOnlineArgs(BaseModel):
    id: int = Field(description="ID of the pool to bring a disk online in.")
    options: PoolLabel = Field(description="Disk identifier to bring online.")


class PoolOnlineResult(BaseModel):
    result: Literal[True] = Field(description="Indicates successful disk online operation.")


class PoolProcessesArgs(BaseModel):
    id: int = Field(description="ID of the pool to get processes for.")


class PoolProcessesResult(BaseModel):
    result: list[PoolProcess] = Field(description="Array of processes currently using the pool.")


class PoolRemoveArgs(BaseModel):
    id: int = Field(description="ID of the pool to remove a disk from.")
    options: PoolLabel = Field(description="Disk identifier to remove from the pool.")


class PoolRemoveResult(BaseModel):
    result: None = Field(description="Returns `null` on successful disk removal.")


class PoolReplaceArgs(BaseModel):
    id: int = Field(description="ID of the pool to replace a disk in.")
    options: PoolReplace = Field(description="Configuration for the disk replacement operation.")


class PoolReplaceResult(BaseModel):
    result: Literal[True] = Field(description="Indicates successful disk replacement initiation.")


class PoolScrubArgs(BaseModel):
    id: int = Field(description="ID of the pool to perform scrub action on.")
    action: Literal["START", "STOP", "PAUSE"] = Field(description="The scrub action to perform.")


class PoolScrubResult(BaseModel):
    result: None = Field(description="Returns `null` on successful scrub action.")


class PoolUpdateArgs(BaseModel):
    id: int = Field(description="ID of the pool to update.")
    data: PoolUpdate = Field(description="Updated configuration for the pool.")


class PoolUpdateResult(BaseModel):
    result: PoolEntry = Field(description="The updated pool configuration.")


class PoolUpgradeArgs(BaseModel):
    id: int = Field(description="ID of the pool to upgrade to the latest feature flags.")


class PoolUpgradeResult(BaseModel):
    result: Literal[True] = Field(description="Indicates successful pool upgrade.")


class PoolValidateNameArgs(BaseModel):
    pool_name: NonEmptyString = Field(description="Pool name to validate for compliance with naming rules.")


class PoolValidateNameResult(BaseModel):
    result: Literal[True] = Field(description="Indicates the pool name is valid.")
