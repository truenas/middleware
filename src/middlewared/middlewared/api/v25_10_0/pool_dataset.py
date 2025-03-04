from typing import Annotated, Any, Literal

from pydantic import Field, Secret

from middlewared.api.base import BaseModel, NonEmptyString, NotRequired, single_argument_args, single_argument_result
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
    "PoolDatasetProcessesResult",
]


class PoolDatasetEntryProperty(BaseModel):
    parsed: Any
    rawvalue: str | None
    value: str | None
    source: str | None
    source_info: Any


class PoolDatasetEntry(BaseModel):
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
    comments: str
    sync: Literal["STANDARD", "ALWAYS", "DISABLED"]
    snapdev: Literal["HIDDEN", "VISIBLE"]
    compression: Literal[
        "ON", "OFF", "LZ4", "GZIP", "GZIP-1", "GZIP-9", "ZSTD", "ZSTD-FAST", "ZLE", "LZJB", "ZSTD-1", "ZSTD-2",
        "ZSTD-3", "ZSTD-4", "ZSTD-5", "ZSTD-6", "ZSTD-7", "ZSTD-8", "ZSTD-9", "ZSTD-10", "ZSTD-11", "ZSTD-12",
        "ZSTD-13", "ZSTD-14", "ZSTD-15", "ZSTD-16", "ZSTD-17", "ZSTD-18", "ZSTD-19", "ZSTD-FAST-1", "ZSTD-FAST-2",
        "ZSTD-FAST-3", "ZSTD-FAST-4", "ZSTD-FAST-5", "ZSTD-FAST-6", "ZSTD-FAST-7", "ZSTD-FAST-8", "ZSTD-FAST-9",
        "ZSTD-FAST-10", "ZSTD-FAST-20", "ZSTD-FAST-30", "ZSTD-FAST-40", "ZSTD-FAST-50", "ZSTD-FAST-60", "ZSTD-FAST-70",
        "ZSTD-FAST-80", "ZSTD-FAST-90", "ZSTD-FAST-100", "ZSTD-FAST-500", "ZSTD-FAST-1000"
    ]
    exec: Literal["ON", "OFF"]
    managedby: NonEmptyString
    quota_warning: Annotated[int, Field(ge=0, le=100)]
    quota_critical: Annotated[int, Field(ge=0, le=100)]
    refquota_warning: Annotated[int, Field(ge=0, le=100)]
    refquota_critical: Annotated[int, Field(ge=0, le=100)]
    reservation: int
    refreservation: int
    special_small_block_size: int | None = None
    copies: int
    snapdir: Literal["DISABLED", "VISIBLE", "HIDDEN"]
    deduplication: Literal["ON", "VERIFY", "OFF"]
    checksum: Literal["ON", "OFF", "FLETCHER2", "FLETCHER4", "SHA256", "SHA512", "SKEIN", "EDONR", "BLAKE3"]
    readonly: Literal["ON", "OFF"]
    share_type: Literal["GENERIC", "MULTIPROTOCOL", "NFS", "SMB", "APPS"] = "GENERIC"
    encryption_options: PoolCreateEncryptionOptions = Field(default_factory=PoolCreateEncryptionOptions)
    encryption: bool = False
    inherit_encryption: bool = True
    user_properties: list[PoolDatasetCreateUserProperty]
    create_ancestors: bool = False


class PoolDatasetCreateFilesystem(PoolDatasetCreate):
    type: Literal["FILESYSTEM"] = "FILESYSTEM"
    aclmode: Literal["PASSTHROUGH", "RESTRICTED", "DISCARD", None] = None
    acltype: Literal["OFF", "NFSV4", "POSIX", None] = None
    atime: Literal["ON", "OFF"]
    casesensitivity: Literal["SENSITIVE", "INSENSITIVE"]
    quota: Annotated[int, Field(ge=1024 ** 3)] | Literal[0, None]
    refquota: Annotated[int, Field(ge=1024 ** 3)] | Literal[0, None]
    recordsize: str | None = None


class PoolDatasetCreateVolume(PoolDatasetCreate):
    type: Literal["VOLUME"] = "VOLUME"
    force_size: bool = False
    sparse: bool = False
    volsize: int
    """The volume size in bytes"""
    volblocksize: Literal["512", "512B", "1K", "2K", "4K", "8K", "16K", "32K", "64K", "128K", None] = None


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


class PoolDatasetRecommendedZVolBlockSizeArgs(BaseModel):
    pool: str


class PoolDatasetRecommendedZVolBlockSizeResult(BaseModel):
    result: str


class PoolDatasetUnlockArgs(BaseModel):
    id: str
    options: PoolDatasetUnlockOptions = Field(default_factory=PoolDatasetUnlockOptions)


class PoolDatasetUnlockResult(BaseModel):
    result: PoolDatasetUnlock
