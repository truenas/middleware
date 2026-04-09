from typing import Annotated, Literal

from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString

__all__ = (
    "ZPoolCreateVdevDRAID",
    "ZPoolCreateVdevNonDRAID",
    "ZPoolCreateTopology",
    "ZPoolCreate",
    "ZPoolCreateArgs",
    "ZPoolCreateResult",
    "ZPoolCreateDataVdev",
)


class ZPoolCreateVdevDRAID(BaseModel):
    type: Literal["DRAID1", "DRAID2", "DRAID3"]
    """Distributed RAID type."""
    disks: list[str] = Field(min_length=2)
    """Disk names (e.g. ``["sda", "sdb", "sdc", ...]``)."""
    draid_data_disks: int = Field(gt=0)
    """Number of data disks per redundancy group."""
    draid_spare_disks: int = Field(ge=0, default=0)
    """Number of distributed spare disks."""


class ZPoolCreateVdevNonDRAID(BaseModel):
    type: Literal["STRIPE", "MIRROR", "RAIDZ1", "RAIDZ2", "RAIDZ3"]
    """Vdev type."""
    disks: list[str] = Field(min_length=1)
    """Disk names (e.g. ``["sda", "sdb"]``)."""


ZPoolCreateDataVdev = Annotated[
    ZPoolCreateVdevDRAID | ZPoolCreateVdevNonDRAID,
    Field(discriminator="type"),
]


class ZPoolCreateTopology(BaseModel):
    data: list[ZPoolCreateDataVdev] = Field(min_length=1)
    """Storage vdevs. All vdevs should share the same type."""
    cache: list[ZPoolCreateVdevNonDRAID] = []
    """L2ARC cache vdevs."""
    log: list[ZPoolCreateVdevNonDRAID] = []
    """ZFS Intent Log (SLOG) vdevs."""
    special: list[ZPoolCreateDataVdev] = []
    """Special allocation class vdevs (metadata/small blocks)."""
    dedup: list[ZPoolCreateDataVdev] = []
    """Dedup table vdevs."""
    spares: list[str] = []
    """Hot spare disk names."""


class ZPoolCreate(BaseModel):
    name: NonEmptyString
    """Pool name."""
    topology: ZPoolCreateTopology
    """Vdev topology for the pool."""
    properties: dict[str, str] = {}
    """Pool properties passed directly to ZFS (e.g. ``{"ashift": "12"}``)."""
    fsoptions: dict[str, str] = {}
    """Root dataset properties passed directly to ZFS (e.g. ``{"compression": "lz4"}``)."""
    allow_duplicate_serials: bool = False
    """Whether to allow disks with duplicate serial numbers."""


class ZPoolCreateArgs(BaseModel):
    data: ZPoolCreate


class ZPoolCreateResult(BaseModel):
    result: None
