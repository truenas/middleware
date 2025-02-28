from typing import Annotated, Any, Literal

from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString
from .pool import PoolCreateEncryptionOptions


__all__ = [
    "PoolDatasetEntry", "PoolDatasetCreateArgs", "PoolDatasetCreateResult", "PoolDatasetDetailsArgs",
    "PoolDatasetDetailsResults"
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


class PoolDatasetCreateArgs(BaseModel):
    data: PoolDatasetCreateFilesystem | PoolDatasetCreateVolume


class PoolDatasetCreateResult(BaseModel):
    result: PoolDatasetEntry


class PoolDatasetDetailsArgs(BaseModel):
    pass


class PoolDatasetDetailsResults(BaseModel):
    result: list[dict]
