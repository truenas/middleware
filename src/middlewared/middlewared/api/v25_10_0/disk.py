from typing import Literal

from middlewared.api.base import BaseModel, NonEmptyString
from .alert import Alert

__all__ = (
    "DiskGetDetailsArgs",
    "DiskGetDetailsResult",
    "DiskGetUsedArgs",
    "DiskGetUsedResult",
    "DiskTemperatureAlertsArgs",
    "DiskTemperatureAlertsResult",
    "DiskWipeArgs",
    "DiskWipeResult",
)


class DiskGetDetails(BaseModel):
    join_partitions: bool = False
    """When True will return all partitions currently
    written to disk.

    NOTE: this is an expensive operation."""
    type: Literal["USED", "UNUSED", "BOTH"] = "BOTH"
    """
    If `USED`, only disks that are IN USE will be returned.
    If `UNUSED`, only disks that are NOT IN USE are returned.
    If `BOTH`, used and unused disks will be returned."""


class DiskGetDetailsArgs(BaseModel):
    data: DiskGetDetails = DiskGetDetails()


class DiskGetDetailsResult(BaseModel):
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
