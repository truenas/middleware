from typing import Annotated, Any, Literal, Union

from pydantic import BeforeValidator, ConfigDict, Field, Secret

from middlewared.api.base import (
    BaseModel, NonEmptyString, NotRequired, single_argument_args, single_argument_result, ForUpdateMetaclass, Excluded,
    excluded_field
)
from middlewared.plugins.zfs_.validation_utils import validate_dataset_name

from .common import QueryFilters, QueryOptions
from .pool import PoolAttachment, PoolCreateEncryptionOptions, PoolProcess


__all__ = [
    "PoolDatasetEntry", "PoolDatasetAttachmentsArgs", "PoolDatasetAttachmentsResult", "PoolDatasetCreateArgs",
    "PoolDatasetCreateResult", "PoolDatasetDetailsArgs", "PoolDatasetDetailsResult",
    "PoolDatasetEncryptionSummaryArgs", "PoolDatasetEncryptionSummaryResult", "PoolDatasetExportKeysArgs",
    "PoolDatasetExportKeysResult", "PoolDatasetExportKeysForReplicationArgs",
    "PoolDatasetExportKeysForReplicationResult", "PoolDatasetExportKeyArgs", "PoolDatasetExportKeyResult",
    "PoolDatasetLockArgs", "PoolDatasetLockResult", "PoolDatasetUnlockArgs", "PoolDatasetUnlockResult",
    "PoolDatasetInsertOrUpdateEncryptedRecordArgs", "PoolDatasetInsertOrUpdateEncryptedRecordResult",
    "PoolDatasetChangeKeyArgs", "PoolDatasetChangeKeyResult", "PoolDatasetInheritParentEncryptionPropertiesArgs",
    "PoolDatasetInheritParentEncryptionPropertiesResult", "PoolDatasetChecksumChoicesArgs",
    "PoolDatasetChecksumChoicesResult", "PoolDatasetCompressionChoicesArgs", "PoolDatasetCompressionChoicesResult",
    "PoolDatasetEncryptionAlgorithmChoicesArgs", "PoolDatasetEncryptionAlgorithmChoicesResult",
    "PoolDatasetRecommendedZvolBlocksizeArgs", "PoolDatasetRecommendedZvolBlocksizeResult", "PoolDatasetProcessesArgs",
    "PoolDatasetProcessesResult", "PoolDatasetGetQuotaArgs", "PoolDatasetGetQuotaResult", "PoolDatasetSetQuotaArgs",
    "PoolDatasetSetQuotaResult", "PoolDatasetRecordsizeChoicesArgs", "PoolDatasetRecordsizeChoicesResult",
    "PoolDatasetUpdateArgs", "PoolDatasetUpdateResult", "PoolDatasetDeleteArgs", "PoolDatasetDeleteResult",
    "PoolDatasetDestroySnapshotsArgs", "PoolDatasetDestroySnapshotsResult", "PoolDatasetPromoteArgs",
    "PoolDatasetPromoteResult", "PoolDatasetRenameArgs", "PoolDatasetRenameResult",
]


def _validate_dataset_name(v: str) -> str:
    if not validate_dataset_name(v):
        raise ValueError('Please provide a valid dataset name according to ZFS standards')
    return v


ZFS_MAX_DATASET_NAME_LEN = 200  # It's really 256, but we should leave some space for snapshot names
DATASET_NAME = Annotated[
    NonEmptyString,
    BeforeValidator(_validate_dataset_name),
]


class PoolDatasetEntryProperty(BaseModel, metaclass=ForUpdateMetaclass):
    parsed: Any
    """The ZFS property value parsed into the appropriate type (string, boolean, integer, etc.)."""
    rawvalue: str | None
    """The raw string value of the ZFS property as stored in the pool. Can be null if not set."""
    value: str | None
    """The current effective value of the ZFS property as a string. Can be null if inherited or not set."""
    source: str | None = Field(examples=['LOCAL', 'INHERITED', 'DEFAULT'])
    """Indicates where the property value originates from."""
    source_info: Any
    """Additional metadata about the property source, such as the parent dataset for inherited values."""


class PoolDatasetEntry(BaseModel, metaclass=ForUpdateMetaclass):
    model_config = ConfigDict(extra="allow", strict=False)
    id: str = Field(examples=['tank/dataset/child'])
    """The full dataset path including pool name."""
    type: str = Field(examples=['FILESYSTEM', 'VOLUME'])
    """The dataset type."""
    name: str
    """The dataset name without the pool prefix."""
    pool: str
    """The name of the ZFS pool containing this dataset."""
    encrypted: bool
    """Whether the dataset is encrypted."""
    encryption_root: str | None
    """The root dataset where encryption is enabled. `null` if the dataset is not encrypted."""
    key_loaded: bool | None
    """Whether the encryption key is currently loaded for encrypted datasets. `null` for unencrypted datasets."""
    children: list
    """Array of child dataset objects nested under this dataset."""
    user_properties: dict
    """Custom user-defined ZFS properties set on this dataset as key-value pairs."""
    locked: bool
    """Whether an encrypted dataset is currently locked (key not loaded)."""
    comments: PoolDatasetEntryProperty
    """ZFS comments property for storing descriptive text about the dataset."""
    quota_warning: PoolDatasetEntryProperty
    """ZFS quota warning threshold property as a percentage."""
    quota_critical: PoolDatasetEntryProperty
    """ZFS quota critical threshold property as a percentage."""
    refquota_warning: PoolDatasetEntryProperty
    """ZFS reference quota warning threshold property as a percentage."""
    refquota_critical: PoolDatasetEntryProperty
    """ZFS reference quota critical threshold property as a percentage."""
    managedby: PoolDatasetEntryProperty
    """Identifies which service or system manages this dataset."""
    deduplication: PoolDatasetEntryProperty
    """ZFS deduplication setting - whether identical data blocks are stored only once."""
    aclmode: PoolDatasetEntryProperty
    """How Access Control Lists (ACLs) are handled when chmod is used."""
    acltype: PoolDatasetEntryProperty
    """The type of Access Control List system used (NFSV4, POSIX, or OFF)."""
    xattr: PoolDatasetEntryProperty
    """Extended attributes storage method (on/off)."""
    atime: PoolDatasetEntryProperty
    """Whether file access times are updated when files are accessed."""
    casesensitivity: PoolDatasetEntryProperty
    """File name case sensitivity setting (sensitive/insensitive)."""
    checksum: PoolDatasetEntryProperty
    """Data integrity checksum algorithm used for this dataset."""
    exec: PoolDatasetEntryProperty
    """Whether files in this dataset can be executed."""
    sync: PoolDatasetEntryProperty
    """Synchronous write behavior (standard/always/disabled)."""
    compression: PoolDatasetEntryProperty
    """Compression algorithm and level applied to data in this dataset."""
    compressratio: PoolDatasetEntryProperty
    """The achieved compression ratio as a decimal (e.g., '2.50x')."""
    origin: PoolDatasetEntryProperty
    """The snapshot from which this clone was created. Empty for non-clone datasets."""
    quota: PoolDatasetEntryProperty
    """Maximum amount of disk space this dataset and its children can consume."""
    refquota: PoolDatasetEntryProperty
    """Maximum amount of disk space this dataset itself can consume (excluding children)."""
    reservation: PoolDatasetEntryProperty
    """Minimum amount of disk space guaranteed to be available to this dataset and its children."""
    refreservation: PoolDatasetEntryProperty
    """Minimum amount of disk space guaranteed to be available to this dataset itself."""
    copies: PoolDatasetEntryProperty
    """Number of copies of data blocks to maintain for redundancy (1-3)."""
    snapdir: PoolDatasetEntryProperty
    """Visibility of the .zfs/snapshot directory (visible/hidden)."""
    readonly: PoolDatasetEntryProperty
    """Whether the dataset is read-only."""
    recordsize: PoolDatasetEntryProperty
    """The suggested block size for files in this filesystem dataset."""
    sparse: PoolDatasetEntryProperty
    """For volumes, whether to use sparse (thin) provisioning."""
    volsize: PoolDatasetEntryProperty
    """For volumes, the logical size of the volume."""
    volblocksize: PoolDatasetEntryProperty
    """For volumes, the block size used by the volume."""
    key_format: PoolDatasetEntryProperty
    """Format of the encryption key (hex/raw/passphrase). Only relevant for encrypted datasets."""
    encryption_algorithm: PoolDatasetEntryProperty
    """Encryption algorithm used (e.g., AES-256-GCM). Only relevant for encrypted datasets."""
    used: PoolDatasetEntryProperty
    """Total amount of disk space consumed by this dataset and all its children."""
    usedbychildren: PoolDatasetEntryProperty
    """Amount of disk space consumed by child datasets."""
    usedbydataset: PoolDatasetEntryProperty
    """Amount of disk space consumed by this dataset itself, excluding children and snapshots."""
    usedbyrefreservation: PoolDatasetEntryProperty
    """Amount of disk space consumed by the refreservation of this dataset."""
    usedbysnapshots: PoolDatasetEntryProperty
    """Amount of disk space consumed by snapshots of this dataset."""
    available: PoolDatasetEntryProperty
    """Amount of disk space available to this dataset and its children."""
    special_small_block_size: PoolDatasetEntryProperty
    """Size threshold below which blocks are stored on special vdevs if configured."""
    pbkdf2iters: PoolDatasetEntryProperty
    """Number of PBKDF2 iterations used for passphrase-based encryption keys."""
    creation: PoolDatasetEntryProperty
    """Timestamp when this dataset was created."""
    snapdev: PoolDatasetEntryProperty
    """Controls visibility of volume snapshots under /dev/zvol/<pool>/."""
    mountpoint: str | None
    """Filesystem path where this dataset is mounted. Null for unmounted datasets or volumes."""


class PoolDatasetChangeKeyOptions(BaseModel):
    generate_key: bool = False
    key_file: bool = False
    pbkdf2iters: int = Field(default=350000, ge=100000)
    passphrase: Secret[NonEmptyString | None] = None
    key: Secret[Annotated[str, Field(min_length=64, max_length=64)] | None] = None


class PoolDatasetCreateUserProperty(BaseModel):
    key: Annotated[str, Field(pattern=".*:.*")]
    value: str


class PoolDatasetCreate(BaseModel):
    name: DATASET_NAME
    comments: str = "INHERIT"
    sync: Literal["STANDARD", "ALWAYS", "DISABLED", "INHERIT"] = "INHERIT"
    snapdev: Literal["HIDDEN", "VISIBLE", "INHERIT"] = NotRequired
    compression: Literal[
        "ON", "OFF", "LZ4", "GZIP", "GZIP-1", "GZIP-9", "ZSTD", "ZSTD-FAST", "ZLE", "LZJB", "ZSTD-1", "ZSTD-2",
        "ZSTD-3", "ZSTD-4", "ZSTD-5", "ZSTD-6", "ZSTD-7", "ZSTD-8", "ZSTD-9", "ZSTD-10", "ZSTD-11", "ZSTD-12",
        "ZSTD-13", "ZSTD-14", "ZSTD-15", "ZSTD-16", "ZSTD-17", "ZSTD-18", "ZSTD-19", "ZSTD-FAST-1", "ZSTD-FAST-2",
        "ZSTD-FAST-3", "ZSTD-FAST-4", "ZSTD-FAST-5", "ZSTD-FAST-6", "ZSTD-FAST-7", "ZSTD-FAST-8", "ZSTD-FAST-9",
        "ZSTD-FAST-10", "ZSTD-FAST-20", "ZSTD-FAST-30", "ZSTD-FAST-40", "ZSTD-FAST-50", "ZSTD-FAST-60", "ZSTD-FAST-70",
        "ZSTD-FAST-80", "ZSTD-FAST-90", "ZSTD-FAST-100", "ZSTD-FAST-500", "ZSTD-FAST-1000", "INHERIT"
    ] = "INHERIT"
    exec: Literal["ON", "OFF", "INHERIT"] = "INHERIT"
    managedby: NonEmptyString = "INHERIT"
    quota_warning: Annotated[int, Field(ge=0, le=100)] | Literal["INHERIT"] = "INHERIT"
    quota_critical: Annotated[int, Field(ge=0, le=100)] | Literal["INHERIT"] = "INHERIT"
    refquota_warning: Annotated[int, Field(ge=0, le=100)] | Literal["INHERIT"] = "INHERIT"
    refquota_critical: Annotated[int, Field(ge=0, le=100)] | Literal["INHERIT"] = "INHERIT"
    reservation: int = NotRequired
    refreservation: int = NotRequired
    special_small_block_size: int | Literal["INHERIT"] = NotRequired
    copies: int | Literal["INHERIT"] = "INHERIT"
    snapdir: Literal["DISABLED", "VISIBLE", "HIDDEN", "INHERIT"] = "INHERIT"
    deduplication: Literal["ON", "VERIFY", "OFF", "INHERIT"] = "INHERIT"
    checksum: Literal[
        "ON", "OFF", "FLETCHER2", "FLETCHER4", "SHA256", "SHA512", "SKEIN", "EDONR", "BLAKE3", "INHERIT"
    ] = "INHERIT"
    readonly: Literal["ON", "OFF", "INHERIT"] = "INHERIT"
    share_type: Literal["GENERIC", "MULTIPROTOCOL", "NFS", "SMB", "APPS"] = "GENERIC"
    encryption_options: PoolCreateEncryptionOptions = Field(default_factory=PoolCreateEncryptionOptions)
    """Configuration for encryption of dataset for `name` pool."""
    encryption: bool = False
    """Create a ZFS encrypted root dataset for `name` pool.
    There is 1 case where ZFS encryption is not allowed for a dataset:
    1) If the parent dataset is encrypted with a passphrase and `name` is being created with a key for encrypting the \
       dataset.
    """
    inherit_encryption: bool = True
    user_properties: list[PoolDatasetCreateUserProperty] = []
    create_ancestors: bool = False


class PoolDatasetCreateFilesystem(PoolDatasetCreate):
    type: Literal["FILESYSTEM"] = "FILESYSTEM"
    aclmode: Literal["PASSTHROUGH", "RESTRICTED", "DISCARD", "INHERIT"] = NotRequired
    acltype: Literal["OFF", "NFSV4", "POSIX", "INHERIT"] = NotRequired
    atime: Literal["ON", "OFF", "INHERIT"] = NotRequired
    casesensitivity: Literal["SENSITIVE", "INSENSITIVE", "INHERIT"] = NotRequired
    quota: Annotated[int, Field(ge=1024 ** 3)] | Literal[0, None] = NotRequired
    refquota: Annotated[int, Field(ge=1024 ** 3)] | Literal[0, None] = NotRequired
    recordsize: str = NotRequired


class PoolDatasetCreateVolume(PoolDatasetCreate):
    type: Literal["VOLUME"] = "VOLUME"
    force_size: bool = NotRequired
    sparse: bool = NotRequired
    volsize: int
    """The volume size in bytes; supposed to be a multiple of the block size."""
    volblocksize: Literal["512", "512B", "1K", "2K", "4K", "8K", "16K", "32K", "64K", "128K"] = NotRequired
    """Defaults to `128K` if the parent pool is a DRAID pool or `16K` otherwise."""


class PoolDatasetDeleteOptions(BaseModel):
    recursive: bool = False
    """Also delete/destroy all children datasets. When root dataset is specified as `id` with `recursive`, it will \
    destroy all the children of the root dataset present leaving root dataset intact."""
    force: bool = False
    """Delete datasets even if they are busy."""


class PoolDatasetEncryptionSummaryOptionsDataset(BaseModel):
    force: bool = False
    name: NonEmptyString
    key: Secret[Annotated[str, Field(min_length=64, max_length=64)]] = NotRequired
    passphrase: Secret[NonEmptyString] = NotRequired


class PoolDatasetEncryptionSummaryOptions(BaseModel):
    key_file: bool = False
    force: bool = False
    datasets: list[PoolDatasetEncryptionSummaryOptionsDataset] = []


class PoolDatasetEncryptionSummary(BaseModel):
    """
    There are 2 keys which show if a recursive unlock operation is done for `id`, which dataset will be unlocked and \
    if not why it won't be unlocked. The keys namely are `unlock_successful` and `unlock_error`. The former is a \
    boolean value showing if unlock would succeed/fail. The latter is description why it failed if it failed.

    In some cases it's possible that the provided key/passphrase is valid but the path where the dataset is supposed \
    to be mounted after being unlocked already exists and is not empty. In this case, unlock operation would fail and \
    `unlock_error` will reflect this error appropriately. This can be overridden by setting \
    `options.datasets.X.force` boolean flag or by setting `options.force` flag. In practice, when the dataset is \
    going to be unlocked and these flags have been provided to `pool.dataset.unlock`, system will rename the \
    directory/file path where the dataset should be mounted resulting in successful unlock of the dataset.

    If a dataset is already unlocked, it will show up as true for "unlock_successful" regardless of what key user \
    provided as the unlock keys in the output are to reflect what a real unlock operation would behave. If user is \
    interested in seeing if a provided key is valid or not, then the key to look out for in the output is "valid_key" \
    which based on what system has in database or if a user provided one, validates the key and sets a boolean value \
    for the dataset.
    """
    name: str
    key_format: str
    key_present_in_database: bool
    valid_key: bool
    locked: bool
    unlock_error: str | None
    unlock_successful: bool


class PoolDatasetLockOptions(BaseModel):
    force_umount: bool = False


class _PoolDatasetQuota(BaseModel, metaclass=ForUpdateMetaclass):
    used_bytes: int
    """The number of bytes the user has written to the dataset. A value of zero means unlimited. May not instantly \
    update as space is used."""
    quota: int
    """The quota size in bytes. Absent if no quota is set."""


class PoolDatasetUserGroupQuota(_PoolDatasetQuota):
    quota_type: Literal['USER', 'GROUP']
    id: int
    """The UID or GID to which the quota applies."""
    name: str | None
    """The user or group name to which the quota applies. Value is null if the id in the quota cannot be resolved to \
    a user or group. This indicates that the user or group does not exist on the server."""
    obj_used: int
    """The number of objects currently owned by `id`."""
    obj_quota: int
    """The number of objects that may be owned by `id`. A value of zero means unlimited. Absent if no objquota is \
    set."""


class PoolDatasetDatasetQuota(_PoolDatasetQuota):
    quota_type: Literal['DATASET']
    id: str
    """Name of the dataset."""
    name: str
    """Name of the dataset."""
    refquota: int


class PoolDatasetProjectQuota(_PoolDatasetQuota):
    quota_type: Literal['PROJECT']
    id: int
    obj_used: int
    """The number of objects currently owned by `id`."""
    obj_quota: int
    """The number of objects that may be owned by `id`. A value of zero means unlimited. Absent if no objquota is \
    set."""


PoolDatasetQuota = Annotated[
    PoolDatasetUserGroupQuota | PoolDatasetDatasetQuota | PoolDatasetProjectQuota,
    Field(discriminator='quota_type')
]


class PoolDatasetSetQuota(BaseModel):
    quota_type: Literal['DATASET', 'USER', 'USEROBJ', 'GROUP', 'GROUPOBJ']
    """The type of quota to apply to the dataset. There are three over-arching types of quotas for ZFS datasets:

    * **Dataset quotas and refquotas.** If a `DATASET` quota type is specified in this API call, then the API acts as \
    a wrapper for `pool.dataset.update`.
    * **User and group quotas.** These limit the amount of disk space consumed by files that are owned by the \
    specified users or groups. If the respective "object quota" type is specfied, then the quota limits the number \
    of objects that may be owned by the specified user or group.
    * **Project quotas.** These limit the amount of disk space consumed by files that are owned by the specified \
    project. *Project quotas are not yet implemented.*
    """
    id: str
    """The UID, GID, or name to which the quota applies. If `quota_type` is 'DATASET', then `id` must be either \
    `QUOTA` or `REFQUOTA`."""
    quota_value: int | None
    """The quota size in bytes. Setting a value of `0` removes the user or group quota."""


class PoolDatasetUnlockOptionsDataset(PoolDatasetEncryptionSummaryOptionsDataset):
    recursive: bool = False
    """Apply the key or passphrase to all encrypted children."""


class PoolDatasetUnlockOptions(BaseModel):
    force: bool = False
    """In some cases it's possible that the provided key/passphrase is valid but the path where the dataset is \
    supposed to be mounted after being unlocked already exists and is not empty. In this case, unlock operation would \
    fail. This can be overridden by setting `datasets.X.force` boolean flag or by setting `force` flag. When any of \
    these flags are set, system will rename the existing directory/file path where the dataset should be mounted \
    resulting in successful unlock of the dataset."""
    key_file: bool = False
    recursive: bool = False
    toggle_attachments: bool = True
    """Whether attachments should be put in action after unlocking the dataset(s). Toggling attachments can \
    theoretically lead to service interruption when daemons configurations are reloaded (this should not happen, and \
    if this happens it should be considered a bug). As TrueNAS does not have a state for resources that should be \
    unlocked but are still locked, disabling this option will put the system into an inconsistent state so it should \
    really never be disabled."""
    datasets: list[PoolDatasetUnlockOptionsDataset] = []


class PoolDatasetUnlock(BaseModel):
    unlocked: list[str]
    """Array of dataset names that were successfully unlocked."""
    failed: dict
    """Object containing datasets that failed to unlock and their respective error messages."""


class PoolDatasetUpdateUserProperty(PoolDatasetCreateUserProperty):
    value: str = NotRequired
    """New value for the user property. Not required if removing the property."""
    remove: bool = NotRequired
    """Whether to remove this user property from the dataset."""


class PoolDatasetUpdate(PoolDatasetCreateFilesystem, PoolDatasetCreateVolume, metaclass=ForUpdateMetaclass):
    name: Excluded = excluded_field()
    type: Excluded = excluded_field()
    casesensitivity: Excluded = excluded_field()
    share_type: Excluded = excluded_field()
    sparse: Excluded = excluded_field()
    volblocksize: Excluded = excluded_field()
    encryption: Excluded = excluded_field()
    encryption_options: Excluded = excluded_field()
    inherit_encryption: Excluded = excluded_field()
    user_properties_update: list[PoolDatasetUpdateUserProperty]


# --------------------   Args and Results   ------------------------ #


class PoolDatasetAttachmentsArgs(BaseModel):
    id: str
    """The dataset ID (full path) to retrieve attachments for."""


class PoolDatasetAttachmentsResult(BaseModel):
    result: list[PoolAttachment]


class PoolDatasetChangeKeyArgs(BaseModel):
    id: str
    """The dataset ID (full path) to change the encryption key for."""
    options: PoolDatasetChangeKeyOptions = Field(default_factory=PoolDatasetChangeKeyOptions)
    """Configuration options for changing the encryption key."""


class PoolDatasetChangeKeyResult(BaseModel):
    result: None


class PoolDatasetChecksumChoicesArgs(BaseModel):
    pass


@single_argument_result
class PoolDatasetChecksumChoicesResult(BaseModel):
    ON: Literal["ON"]
    FLETCHER2: Literal["FLETCHER2"]
    FLETCHER4: Literal["FLETCHER4"]
    SHA256: Literal["SHA256"]
    SHA512: Literal["SHA512"]
    SKEIN: Literal["SKEIN"]
    EDONR: Literal["EDONR"]
    BLAKE3: Literal["BLAKE3"]


class PoolDatasetCompressionChoicesArgs(BaseModel):
    pass


class PoolDatasetCompressionChoicesResult(BaseModel):
    result: dict[str, str]


class PoolDatasetCreateArgs(BaseModel):
    data: PoolDatasetCreateFilesystem | PoolDatasetCreateVolume


class PoolDatasetCreateResult(BaseModel):
    result: PoolDatasetEntry


class PoolDatasetDeleteArgs(BaseModel):
    id: str
    options: PoolDatasetDeleteOptions = Field(default_factory=PoolDatasetDeleteOptions)


class PoolDatasetDeleteResult(BaseModel):
    result: Literal[None, True]
    """Return true on successful deletion or null if the `zfs destroy` command fails with "dataset does not exist"."""


class PoolDatasetDetailsArgs(BaseModel):
    """Get detailed information about all datasets."""
    pass


class PoolDatasetDetailsResult(BaseModel):
    result: list[dict]
    """Array of detailed dataset information objects."""


class PoolDatasetEncryptionAlgorithmChoicesArgs(BaseModel):
    pass


@single_argument_result
class PoolDatasetEncryptionAlgorithmChoicesResult(BaseModel):
    AES_128_CCM: Literal["AES-128-CCM"] = Field(alias="AES-128-CCM")
    AES_192_CCM: Literal["AES-192-CCM"] = Field(alias="AES-192-CCM")
    AES_256_CCM: Literal["AES-256-CCM"] = Field(alias="AES-256-CCM")
    AES_128_GCM: Literal["AES-128-GCM"] = Field(alias="AES-128-GCM")
    AES_192_GCM: Literal["AES-192-GCM"] = Field(alias="AES-192-GCM")
    AES_256_GCM: Literal["AES-256-GCM"] = Field(alias="AES-256-GCM")


class PoolDatasetEncryptionSummaryArgs(BaseModel):
    id: str
    """The dataset ID (full path) to generate an encryption summary for."""
    options: PoolDatasetEncryptionSummaryOptions = Field(default_factory=PoolDatasetEncryptionSummaryOptions)
    """Options for generating the encryption summary including force settings and datasets."""


class PoolDatasetEncryptionSummaryResult(BaseModel):
    result: list[PoolDatasetEncryptionSummary]


class PoolDatasetExportKeyArgs(BaseModel):
    id: str
    """The dataset ID (full path) to export the encryption key from."""
    download: bool = False
    """Whether to prepare the key for download as a file."""


class PoolDatasetExportKeyResult(BaseModel):
    result: Secret[str | None]


class PoolDatasetExportKeysArgs(BaseModel):
    id: str
    """The dataset ID (full path) to export keys from recursively."""


class PoolDatasetExportKeysResult(BaseModel):
    result: None


class PoolDatasetExportKeysForReplicationArgs(BaseModel):
    id: int
    """The pool ID to export dataset keys for replication purposes."""


class PoolDatasetExportKeysForReplicationResult(BaseModel):
    result: None


class PoolDatasetGetQuotaArgs(BaseModel):
    dataset: str
    """The dataset path to retrieve quotas for."""
    quota_type: Literal['USER', 'GROUP', 'DATASET', 'PROJECT']
    """The type of quotas to retrieve."""
    filters: QueryFilters = []
    """Query filters to limit the results returned."""
    options: QueryOptions = Field(default_factory=QueryOptions)
    """Query options such as sorting and pagination."""


class PoolDatasetGetQuotaResult(BaseModel):
    result: list[PoolDatasetQuota]


class PoolDatasetInheritParentEncryptionPropertiesArgs(BaseModel):
    id: str
    """The dataset ID (full path) to inherit encryption properties from its parent."""


class PoolDatasetInheritParentEncryptionPropertiesResult(BaseModel):
    result: None


@single_argument_args("data")
class PoolDatasetInsertOrUpdateEncryptedRecordArgs(BaseModel):
    encryption_key: Any = None
    """The encryption key data to insert or update."""
    id: int | None = None
    """The record ID for updates, or null for new records."""
    name: NonEmptyString
    """The dataset name for the encryption record."""
    key_format: str | None = Field(examples=['hex', 'raw', 'passphrase'])
    """The format of the encryption key."""


class PoolDatasetInsertOrUpdateEncryptedRecordResult(BaseModel):
    result: str | None


class PoolDatasetLockArgs(BaseModel):
    id: str
    """The dataset ID (full path) to lock."""
    options: PoolDatasetLockOptions = Field(default_factory=PoolDatasetLockOptions)
    """Options for locking the dataset, such as force unmount settings."""


class PoolDatasetLockResult(BaseModel):
    result: Literal[True]
    """Dataset is locked."""


class PoolDatasetProcessesArgs(BaseModel):
    id: str
    """The dataset ID (full path) to list processes for."""


class PoolDatasetProcessesResult(BaseModel):
    result: list[PoolProcess]


class PoolDatasetPromoteArgs(BaseModel):
    id: str
    """The clone dataset ID (full path) to promote to become the parent."""


class PoolDatasetPromoteResult(BaseModel):
    result: None


class PoolDatasetRecommendedZvolBlocksizeArgs(BaseModel):
    pool: str
    """The pool name to get the recommended volume block size for."""


class PoolDatasetRecommendedZvolBlocksizeResult(BaseModel):
    result: str


class PoolDatasetRecordsizeChoicesArgs(BaseModel):
    pool_name: str | None = None
    """Optional pool name to get record size choices for. If not provided, returns general choices."""


class PoolDatasetRecordsizeChoicesResult(BaseModel):
    result: list[str]


class PoolDatasetSetQuotaArgs(BaseModel):
    dataset: str
    """The name of the target ZFS dataset."""
    quotas: list[PoolDatasetSetQuota] = Field(
        max_length=100,
        default=[PoolDatasetSetQuota(quota_type='USER', id='0', quota_value=0)]
    )
    """Specify an array of quota entries to apply to dataset. The array may contain all supported quota types."""


class PoolDatasetSetQuotaResult(BaseModel):
    result: None


class PoolDatasetUnlockArgs(BaseModel):
    id: str
    """The dataset ID (full path) to unlock."""
    options: PoolDatasetUnlockOptions = Field(default_factory=PoolDatasetUnlockOptions)
    """Options for unlocking including force settings, recursion, and dataset-specific keys."""


class PoolDatasetUnlockResult(BaseModel):
    result: PoolDatasetUnlock


class PoolDatasetDestroySnapshotsArgs(BaseModel):
    name: str
    """The dataset name to destroy snapshots for."""
    snapshots: "PoolDatasetDestroySnapshotsArgsSnapshots"
    """Specification of which snapshots to destroy (all, specific ones, or ranges)."""


class PoolDatasetDestroySnapshotsArgsSnapshots(BaseModel):
    all: bool = False
    """Whether to destroy all snapshots for the dataset."""
    recursive: bool = False
    """Whether to recursively destroy snapshots of child datasets."""
    snapshots: list[Union["PoolDatasetDestroySnapshotsArgsSnapshotSpec", str]] = []
    """Array of specific snapshot names or snapshot range specifications to destroy."""


class PoolDatasetDestroySnapshotsArgsSnapshotSpec(BaseModel):
    start: str | None = None
    """Starting snapshot name for the range. Null to start from the beginning."""
    end: str | None = None
    """Ending snapshot name for the range. Null to continue to the end."""


class PoolDatasetDestroySnapshotsResult(BaseModel):
    result: list[str]


class PoolDatasetUpdateArgs(BaseModel):
    id: str
    """The dataset ID (full path) to update."""
    data: PoolDatasetUpdate
    """The dataset properties to update."""


class PoolDatasetUpdateResult(BaseModel):
    result: PoolDatasetEntry


class PoolDatasetRenameOptions(BaseModel):
    new_name: DATASET_NAME
    """The new name for the dataset."""
    recursive: bool = False
    """Whether to recursively rename child datasets."""
    force: bool = False
    """
    This operation does not check whether the dataset is currently in use. Renaming an active dataset may disrupt \
    SMB shares, iSCSI targets, snapshots, replication, and other services.

    Set Force only if you understand and accept the risks.
    """


class PoolDatasetRenameArgs(BaseModel):
    id: NonEmptyString
    """The current dataset ID (full path) to rename."""
    data: PoolDatasetRenameOptions
    """The rename operation options including the new name and safety flags."""


class PoolDatasetRenameResult(BaseModel):
    result: None
