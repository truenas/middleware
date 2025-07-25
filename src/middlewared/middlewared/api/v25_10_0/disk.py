from datetime import datetime
from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import BaseModel, NonEmptyString, NotRequired, ForUpdateMetaclass, Excluded, excluded_field
from .alert import Alert

__all__ = (
    "DiskEntry",
    "DiskDetailsArgs",
    "DiskDetailsResult",
    "DiskGetUsedArgs",
    "DiskGetUsedResult",
    "DiskTemperaturesArgs",
    "DiskTemperaturesResult",
    "DiskTemperatureAggArgs",
    "DiskTemperatureAggResult",
    "DiskTemperatureAlertsArgs",
    "DiskTemperatureAlertsResult",
    "DiskUpdateArgs",
    "DiskUpdateResult",
    "DiskWipeArgs",
    "DiskWipeResult",
)


class DiskEntryEnclosure(BaseModel):
    number: int
    """Enclosure number where the disk is located."""
    slot: int
    """Physical slot position within the enclosure."""


class DiskEntry(BaseModel):
    identifier: str
    """Unique identifier for the disk device."""
    name: str
    """System name of the disk device."""
    subsystem: str = Field(examples=["SCSI", "ATA"])
    """Storage subsystem type."""
    number: int
    """Numeric identifier assigned to the disk."""
    serial: str
    """Manufacturer serial number of the disk."""
    lunid: str | None
    size: int | None
    """Total size of the disk in bytes. `null` if not available."""
    description: str
    """Human-readable description of the disk device."""
    transfermode: str
    hddstandby: Literal["ALWAYS ON", "5", "10", "20", "30", "60", "120", "180", "240", "300", "330"]
    advpowermgmt: Literal["DISABLED", "1", "64", "127", "128", "192", "254"]
    expiretime: datetime | None
    model: str | None
    """Manufacturer model name/number of the disk. `null` if not available."""
    rotationrate: int | None
    type: str | None
    zfs_guid: str | None
    bus: str
    devname: str = Field(examples=["/dev/sda"])
    """Device name in the operating system."""
    enclosure: DiskEntryEnclosure | None
    pool: str | None
    """Name of the storage pool this disk belongs to. `null` if not part of any pool."""
    passwd: Secret[str] = NotRequired
    kmip_uid: str | None = NotRequired


class DiskDetails(BaseModel):
    join_partitions: bool = False
    """Return all partitions currently written to disk.

    **NOTE: This is an expensive operation.**
    """
    type: Literal["USED", "UNUSED", "BOTH"] = "BOTH"
    """
    * `USED`: Only disks that are IN USE will be returned.
    * `UNUSED`: Only disks that are NOT IN USE are returned.
    * `BOTH`: Used and unused disks will be returned.
    """


class DiskUpdate(DiskEntry, metaclass=ForUpdateMetaclass):
    identifier: Excluded = excluded_field()
    name: Excluded = excluded_field()
    subsystem: Excluded = excluded_field()
    serial: Excluded = excluded_field()
    kmip_uid: Excluded = excluded_field()
    size: Excluded = excluded_field()
    transfermode: Excluded = excluded_field()
    expiretime: Excluded = excluded_field()
    model: Excluded = excluded_field()
    rotationrate: Excluded = excluded_field()
    type: Excluded = excluded_field()
    zfs_guid: Excluded = excluded_field()
    devname: Excluded = excluded_field()


class DiskDetailsArgs(BaseModel):
    data: DiskDetails = Field(default_factory=DiskDetails)


class DiskDetailsResult(BaseModel):
    result: list | dict


class DiskGetUsedArgs(BaseModel):
    join_partitions: bool = False
    """Return all partitions currently written to disk.

    **NOTE: this is an expensive operation.**
    """


class DiskGetUsedResult(BaseModel):
    result: list


class DiskTemperaturesArgs(BaseModel):
    name: list[str] = Field(default_factory=list)
    """
    List of names of disks to retrieve temperature information. Name should be in the form of "sda", "nvme0n1", etc.
    """
    include_thresholds: bool = False
    """Include the temperature thresholds as reported by the disk (i.e. the critical temp)."""


class DiskTemperaturesResult(BaseModel):
    result: dict


class DiskTemperatureAggArgs(BaseModel):
    names: list[str]
    days: int = 7


class DiskTemperatureAggEntry(BaseModel):
    min_: int | float | None = Field(alias="min")
    max_: int | float | None = Field(alias="max")
    avg: int | float | None


class DiskTemperatureAggResult(BaseModel):
    result: dict[str, DiskTemperatureAggEntry]


class DiskTemperatureAlertsArgs(BaseModel):
    names: list[str]


class DiskTemperatureAlertsResult(BaseModel):
    result: list[Alert]


class DiskUpdateArgs(BaseModel):
    id: str
    data: DiskUpdate


class DiskUpdateResult(BaseModel):
    result: DiskEntry


class DiskWipeArgs(BaseModel):
    dev: NonEmptyString
    """The device to perform the disk wipe operation on. May be passed as /dev/sda or just sda."""
    mode: Literal["QUICK", "FULL", "FULL_RANDOM"]
    """
    * QUICK: Write zeros to the first and last 32MB of device.
    * FULL: Write whole disk with zeros.
    * FULL_RANDOM: Write whole disk with random bytes.
    """
    synccache: bool = True
    """Synchronize the device with the database."""


class DiskWipeResult(BaseModel):
    result: None
