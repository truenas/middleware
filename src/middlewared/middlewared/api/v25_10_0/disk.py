from datetime import datetime
from typing import Literal

from pydantic import Field, SecretStr

from middlewared.api.base import BaseModel, NonEmptyString, NotRequired, ForUpdateMetaclass, Excluded, excluded_field
from .alert import Alert

__all__ = (
    "DiskEntry",
    "DiskDetailsArgs",
    "DiskDetailsResult",
    "DiskGetUsedArgs",
    "DiskGetUsedResult",
    "DiskTemperatureAlertsArgs",
    "DiskTemperatureAlertsResult",
    "DiskUpdateArgs",
    "DiskUpdateResult",
    "DiskWipeArgs",
    "DiskWipeResult",
)


class DiskEntryEnclosure(BaseModel):
    number: int = NotRequired
    slot: int = NotRequired


class DiskEntry(BaseModel):
    identifier: str
    name: str
    subsystem: str
    number: int
    serial: str
    lunid: str | None
    size: int
    description: str
    transfermode: str
    hddstandby: Literal["ALWAYS ON", "5", "10", "20", "30", "60", "120", "180", "240", "300", "330"]
    advpowermgmt: Literal["DISABLED", "1", "64", "127", "128", "192", "254"]
    expiretime: datetime | None
    model: str | None
    rotationrate: int | None
    type: str | None
    zfs_guid: str | None
    bus: str
    devname: str
    enclosure: DiskEntryEnclosure | None
    pool: str | None
    passwd: SecretStr = NotRequired
    kmip_uid: str | None = NotRequired


class DiskDetails(BaseModel):
    join_partitions: bool = False
    """When True will return all partitions currently
    written to disk.

    NOTE: this is an expensive operation."""
    type: Literal["USED", "UNUSED", "BOTH"] = "BOTH"
    """
    If `USED`, only disks that are IN USE will be returned.
    If `UNUSED`, only disks that are NOT IN USE are returned.
    If `BOTH`, used and unused disks will be returned.
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
    """When True will return all partitions currently
    written to disk.

    NOTE: this is an expensive operation."""


class DiskGetUsedResult(BaseModel):
    result: list


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
    """The device to perform the disk wipe operation on.
    May be passed as /dev/sda or just sda."""
    mode: Literal["QUICK", "FULL", "FULL_RANDOM"]
    """
    QUICK: write zeros to the first and last 32MB of device
    FULL: write whole disk with zero's
    FULL_RANDOM: write whole disk with random bytes
    """
    synccache: bool = True
    """If True, will synchronize the device with the database"""


class DiskWipeResult(BaseModel):
    result: None
