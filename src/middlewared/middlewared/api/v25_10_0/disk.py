from typing import Literal

from middlewared.api.base import BaseModel, NonEmptyString
from .alert import Alert

__all__ = (
    "DiskTemperatureAlertsArgs",
    "DiskTemperatureAlertsResult",
    "DiskWipeArgs",
    "DiskWipeResult",
)


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
