from typing import Literal

from pydantic import Field, PositiveInt

from middlewared.api.base import BaseModel, NonEmptyString

from .pool import PoolCreateTopology
from .zpool_query import ZPoolEntry

__all__ = [
    "ZPoolCreate",
    "ZPoolCreateArgs",
    "ZPoolCreateResult",
]


class ZPoolCreate(BaseModel):
    name: NonEmptyString = Field(description="Name for the new storage pool.")
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
            "signatures, byte-to-byte comparison is performed to ensure that the blocks are identical. This should be "
            "used in special circumstances as it carries a significant overhead."
        ),
    )
    checksum: Literal[
        "ON", "OFF", "FLETCHER2", "FLETCHER4", "SHA256", "SHA512", "SKEIN", "EDONR", "BLAKE3", None
    ] = Field(default=None, description="Checksum algorithm to use for data integrity verification.")
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


class ZPoolCreateArgs(BaseModel):
    data: ZPoolCreate = Field(description="Configuration for the new ZFS pool to create.")


class ZPoolCreateResult(BaseModel):
    result: ZPoolEntry = Field(description="The newly created ZFS pool.")
