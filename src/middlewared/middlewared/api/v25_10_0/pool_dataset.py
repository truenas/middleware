from typing import Annotated, Any, Literal

from pydantic import Field, Secret

from middlewared.api.base import (
    BaseModel, NonEmptyString, NotRequired, single_argument_args, single_argument_result, ForUpdateMetaclass, Excluded,
    excluded_field
)
from .common import QueryFilters, QueryOptions
from .pool import PoolAttachment, PoolCreateEncryptionOptions, PoolProcess


__all__ = [
    "PoolDatasetEntry", "PoolDatasetAttachmentsArgs", "PoolDatasetAttachmentsResult", "PoolDatasetCreateArgs",
    "PoolDatasetCreateResult", "PoolDatasetDetailsArgs", "PoolDatasetDetailsResults",
    "PoolDatasetEncryptionSummaryArgs", "PoolDatasetEncryptionSummaryResult", "PoolDatasetExportKeysArgs",
    "PoolDatasetExportKeysResult", "PoolDatasetExportKeysForReplicationArgs",
    "PoolDatasetExportKeysForReplicationResult", "PoolDatasetExportKeyArgs", "PoolDatasetExportKeyResult",
    "PoolDatasetLockArgs", "PoolDatasetLockResult", "PoolDatasetUnlockArgs", "PoolDatasetUnlockResult",
    "PoolDatasetInsertOrUpdateEncryptedRecordArgs", "PoolDatasetInsertOrUpdateEncryptedRecordResult",
    "PoolDatasetChangeKeyArgs", "PoolDatasetChangeKeyResult", "PoolDatasetInheritParentEncryptionPropertiesArgs",
    "PoolDatasetInheritParentEncryptionPropertiesResult", "PoolDatasetChecksumChoicesArgs",
    "PoolDatasetChecksumChoicesResult", "PoolDatasetCompressionChoicesArgs", "PoolDatasetCompressionChoicesResult",
    "PoolDatasetEncryptionAlgorithmChoicesArgs", "PoolDatasetEncryptionAlgorithmChoicesResult",
    "PoolDatasetRecommendedZVolBlockSizeArgs", "PoolDatasetRecommendedZVolBlockSizeResult", "PoolDatasetProcessesArgs",
    "PoolDatasetProcessesResult", "PoolDatasetGetQuotaArgs", "PoolDatasetGetQuotaResult", "PoolDatasetSetQuotaArgs",
    "PoolDatasetSetQuotaResult", "PoolDatasetRecordSizeChoicesArgs", "PoolDatasetRecordSizeChoicesResult",
    "PoolDatasetUpdateArgs", "PoolDatasetUpdateResult", "PoolDatasetDeleteArgs", "PoolDatasetDeleteResult",
    "PoolDatasetPromoteArgs", "PoolDatasetPromoteResult",
]


class PoolDatasetEntryProperty(BaseModel, metaclass=ForUpdateMetaclass):
    parsed: Any
    rawvalue: str | None
    value: str | None
    source: str | None
    source_info: Any


class PoolDatasetEntry(BaseModel, metaclass=ForUpdateMetaclass):
    id: str
    type: str
    name: str
    pool: str
    encrypted: bool
    encryption_root: str | None
    key_loaded: bool | None
    children: list
    user_properties: dict
    locked: bool
    comments: PoolDatasetEntryProperty
    quota_warning: PoolDatasetEntryProperty
    quota_critical: PoolDatasetEntryProperty
    refquota_warning: PoolDatasetEntryProperty
    refquota_critical: PoolDatasetEntryProperty
    managedby: PoolDatasetEntryProperty
    deduplication: PoolDatasetEntryProperty
    aclmode: PoolDatasetEntryProperty
    acltype: PoolDatasetEntryProperty
    xattr: PoolDatasetEntryProperty
    atime: PoolDatasetEntryProperty
    casesensitivity: PoolDatasetEntryProperty
    checksum: PoolDatasetEntryProperty
    exec: PoolDatasetEntryProperty
    sync: PoolDatasetEntryProperty
    compression: PoolDatasetEntryProperty
    compressratio: PoolDatasetEntryProperty
    origin: PoolDatasetEntryProperty
    quota: PoolDatasetEntryProperty
    refquota: PoolDatasetEntryProperty
    reservation: PoolDatasetEntryProperty
    refreservation: PoolDatasetEntryProperty
    copies: PoolDatasetEntryProperty
    snapdir: PoolDatasetEntryProperty
    readonly: PoolDatasetEntryProperty
    recordsize: PoolDatasetEntryProperty
    sparse: PoolDatasetEntryProperty
    volsize: PoolDatasetEntryProperty
    volblocksize: PoolDatasetEntryProperty
    key_format: PoolDatasetEntryProperty
    encryption_algorithm: PoolDatasetEntryProperty
    used: PoolDatasetEntryProperty
    usedbychildren: PoolDatasetEntryProperty
    usedbydataset: PoolDatasetEntryProperty
    usedbyrefreservation: PoolDatasetEntryProperty
    usedbysnapshots: PoolDatasetEntryProperty
    available: PoolDatasetEntryProperty
    special_small_block_size: PoolDatasetEntryProperty
    pbkdf2iters: PoolDatasetEntryProperty
    creation: PoolDatasetEntryProperty
    snapdev: PoolDatasetEntryProperty
    mountpoint: str | None


class PoolDatasetChangeKeyOptions(BaseModel):
    generate_key: bool = False
    key_file: bool = False
    pbkdf2iters: int = Field(default=350000, ge=100000)
    passphrase: Secret[NonEmptyString | None] = None
    key: Secret[Annotated[str, Field(min_length=64, max_length=64)] | None] = None


class PoolDatasetCreateUserProperty(BaseModel):
    key: Annotated[str, Field(pattern=r".*:.*")]
    value: str


class PoolDatasetCreate(BaseModel):
    name: Annotated[str, Field(max_length=200)]
    comments: str = "INHERIT"
    sync: Literal["STANDARD", "ALWAYS", "DISABLED"] = "INHERIT"
    snapdev: Literal["HIDDEN", "VISIBLE"] = NotRequired
    compression: Literal[
        "ON", "OFF", "LZ4", "GZIP", "GZIP-1", "GZIP-9", "ZSTD", "ZSTD-FAST", "ZLE", "LZJB", "ZSTD-1", "ZSTD-2",
        "ZSTD-3", "ZSTD-4", "ZSTD-5", "ZSTD-6", "ZSTD-7", "ZSTD-8", "ZSTD-9", "ZSTD-10", "ZSTD-11", "ZSTD-12",
        "ZSTD-13", "ZSTD-14", "ZSTD-15", "ZSTD-16", "ZSTD-17", "ZSTD-18", "ZSTD-19", "ZSTD-FAST-1", "ZSTD-FAST-2",
        "ZSTD-FAST-3", "ZSTD-FAST-4", "ZSTD-FAST-5", "ZSTD-FAST-6", "ZSTD-FAST-7", "ZSTD-FAST-8", "ZSTD-FAST-9",
        "ZSTD-FAST-10", "ZSTD-FAST-20", "ZSTD-FAST-30", "ZSTD-FAST-40", "ZSTD-FAST-50", "ZSTD-FAST-60", "ZSTD-FAST-70",
        "ZSTD-FAST-80", "ZSTD-FAST-90", "ZSTD-FAST-100", "ZSTD-FAST-500", "ZSTD-FAST-1000"
    ] = "INHERIT"
    exec: Literal["ON", "OFF"] = "INHERIT"
    managedby: NonEmptyString = "INHERIT"
    quota_warning: Annotated[int, Field(ge=0, le=100)] = "INHERIT"
    quota_critical: Annotated[int, Field(ge=0, le=100)] = "INHERIT"
    refquota_warning: Annotated[int, Field(ge=0, le=100)] = "INHERIT"
    refquota_critical: Annotated[int, Field(ge=0, le=100)] = "INHERIT"
    reservation: int = NotRequired
    refreservation: int = NotRequired
    special_small_block_size: int = NotRequired
    copies: int = "INHERIT"
    snapdir: Literal["DISABLED", "VISIBLE", "HIDDEN"] = "INHERIT"
    deduplication: Literal["ON", "VERIFY", "OFF"] = "INHERIT"
    checksum: Literal["ON", "OFF", "FLETCHER2", "FLETCHER4", "SHA256", "SHA512", "SKEIN", "EDONR", "BLAKE3"] = "INHERIT"
    readonly: Literal["ON", "OFF"] = "INHERIT"
    share_type: Literal["GENERIC", "MULTIPROTOCOL", "NFS", "SMB", "APPS"] = "GENERIC"
    encryption_options: PoolCreateEncryptionOptions = Field(default_factory=PoolCreateEncryptionOptions)
    encryption: bool = False
    inherit_encryption: bool = True
    user_properties: list[PoolDatasetCreateUserProperty] = []
    create_ancestors: bool = False


class PoolDatasetCreateFilesystem(PoolDatasetCreate):
    type: Literal["FILESYSTEM"] = "FILESYSTEM"
    aclmode: Literal["PASSTHROUGH", "RESTRICTED", "DISCARD"] = NotRequired
    acltype: Literal["OFF", "NFSV4", "POSIX"] = NotRequired
    atime: Literal["ON", "OFF"] = NotRequired
    casesensitivity: Literal["SENSITIVE", "INSENSITIVE"] = NotRequired
    quota: Annotated[int, Field(ge=1024 ** 3)] | Literal[0, None] = NotRequired
    refquota: Annotated[int, Field(ge=1024 ** 3)] | Literal[0, None] = NotRequired
    recordsize: str = NotRequired


class PoolDatasetCreateVolume(PoolDatasetCreate):
    type: Literal["VOLUME"]
    force_size: bool = NotRequired
    sparse: bool = NotRequired
    volsize: int = NotRequired
    """The volume size in bytes"""
    volblocksize: Literal["512", "512B", "1K", "2K", "4K", "8K", "16K", "32K", "64K", "128K"] = NotRequired


class PoolDatasetDeleteOptions(BaseModel):
    recursive: bool = False
    """Also delete/destroy all children datasets. When root dataset is specified as `id` with `recursive`, it will
    destroy all the children of the root dataset present leaving root dataset intact."""
    force: bool = False
    """Force delete busy datasets."""


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
    """The number of bytes the user has written to the dataset. A value of zero means unlimited. May not instantly
    update as space is used."""
    quota: int
    """The quota size in bytes. Absent if no quota is set."""


class PoolDatasetUserGroupQuota(_PoolDatasetQuota):
    quota_type: Literal['USER', 'GROUP']
    id: str
    """The UID or GID to which the quota applies."""
    name: str | None
    """The user or group name to which the quota applies. Value is null if the id in the quota cannot be resolved to a
    user or group. This indicates that the user or group does not exist on the server."""
    obj_used: int
    """The number of objects currently owned by `id`."""
    obj_quota: int
    """The number of objects that may be owned by `id`. A value of zero means unlimited. Absent if no objquota is
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
    """The number of objects that may be owned by `id`. A value of zero means unlimited. Absent if no objquota is
    set."""


PoolDatasetQuota = Annotated[
    PoolDatasetUserGroupQuota | PoolDatasetDatasetQuota | PoolDatasetProjectQuota,
    Field(discriminator='quota_type')
]


class PoolDatasetSetQuota(BaseModel):
    quota_type: Literal['DATASET', 'USER', 'USEROBJ', 'GROUP', 'GROUPOBJ']
    """The type of quota to apply to the dataset. `USEROBJ` and `GROUPOBJ` quotas limit the number of objects consumed
    by the specified user or group."""
    id: str
    """The UID, GID, or name to which the quota applies. If `quota_type` is 'DATASET', then `id` must be either `QUOTA`
    or `REFQUOTA`."""
    quota_value: int | None
    """The quota size in bytes. Setting a value of `0` removes the user or group quota."""


class PoolDatasetUnlockOptionsDataset(PoolDatasetEncryptionSummaryOptionsDataset):
    recursive: bool = False


class PoolDatasetUnlockOptions(BaseModel):
    force: bool = False
    key_file: bool = False
    recursive: bool = False
    toggle_attachments: bool = True
    datasets: list[PoolDatasetUnlockOptionsDataset] = []


class PoolDatasetUnlock(BaseModel):
    unlocked: list[str]
    failed: dict


class PoolDatasetUpdateUserProperty(PoolDatasetCreateUserProperty):
    value: str = NotRequired
    remove: bool = NotRequired


class PoolDatasetUpdate(PoolDatasetCreate, metaclass=ForUpdateMetaclass):
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


##############################   Args and Results   #############################################


class PoolDatasetAttachmentsArgs(BaseModel):
    id: str


class PoolDatasetAttachmentsResult(BaseModel):
    result: list[PoolAttachment]


class PoolDatasetChangeKeyArgs(BaseModel):
    id: str
    options: PoolDatasetChangeKeyOptions = Field(default_factory=PoolDatasetChangeKeyOptions)


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
    pass


class PoolDatasetDetailsResults(BaseModel):
    result: list[dict]


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
    options: PoolDatasetEncryptionSummaryOptions = Field(default_factory=PoolDatasetEncryptionSummaryOptions)


class PoolDatasetEncryptionSummaryResult(BaseModel):
    result: list[PoolDatasetEncryptionSummary]


class PoolDatasetExportKeyArgs(BaseModel):
    id: str
    download: bool = False


class PoolDatasetExportKeyResult(BaseModel):
    result: Secret[str | None]


class PoolDatasetExportKeysArgs(BaseModel):
    id: str


class PoolDatasetExportKeysResult(BaseModel):
    result: None


class PoolDatasetExportKeysForReplicationArgs(BaseModel):
    id: int


class PoolDatasetExportKeysForReplicationResult(BaseModel):
    result: None


class PoolDatasetGetQuotaArgs(BaseModel):
    dataset: str
    quota_type: Literal['USER', 'GROUP', 'DATASET', 'PROJECT']
    filters: QueryFilters = []
    options: QueryOptions = Field(default_factory=QueryOptions)


class PoolDatasetGetQuotaResult(BaseModel):
    result: list[PoolDatasetQuota]


class PoolDatasetInheritParentEncryptionPropertiesArgs(BaseModel):
    id: str


class PoolDatasetInheritParentEncryptionPropertiesResult(BaseModel):
    result: None


@single_argument_args("data")
class PoolDatasetInsertOrUpdateEncryptedRecordArgs(BaseModel):
    encryption_key: Any = None
    id: int | None = None
    name: NonEmptyString
    key_format: str | None


class PoolDatasetInsertOrUpdateEncryptedRecordResult(BaseModel):
    result: str | None


class PoolDatasetLockArgs(BaseModel):
    id: str
    options: PoolDatasetLockOptions = Field(default_factory=PoolDatasetLockOptions)


class PoolDatasetLockResult(BaseModel):
    result: Literal[True]
    """Dataset is locked."""


class PoolDatasetProcessesArgs(BaseModel):
    id: str


class PoolDatasetProcessesResult(BaseModel):
    result: list[PoolProcess]


class PoolDatasetPromoteArgs(BaseModel):
    id: str


class PoolDatasetPromoteResult(BaseModel):
    result: None


class PoolDatasetRecommendedZVolBlockSizeArgs(BaseModel):
    pool: str


class PoolDatasetRecommendedZVolBlockSizeResult(BaseModel):
    result: str


class PoolDatasetRecordSizeChoicesArgs(BaseModel):
    pool_name: str | None = None


class PoolDatasetRecordSizeChoicesResult(BaseModel):
    result: list[str]


class PoolDatasetSetQuotaArgs(BaseModel):
    dataset: str
    """The name of the target ZFS dataset."""
    quotas: list[PoolDatasetSetQuota] = [PoolDatasetSetQuota(quota_type='USER', id='0', quota_value=0)]
    """Specify an array of quota entries to apply to dataset."""


class PoolDatasetSetQuotaResult(BaseModel):
    result: None


class PoolDatasetUnlockArgs(BaseModel):
    id: str
    options: PoolDatasetUnlockOptions = Field(default_factory=PoolDatasetUnlockOptions)


class PoolDatasetUnlockResult(BaseModel):
    result: PoolDatasetUnlock


class PoolDatasetUpdateArgs(BaseModel):
    id: str
    data: PoolDatasetUpdate


class PoolDatasetUpdateResult(BaseModel):
    result: PoolDatasetEntry
