from datetime import datetime
from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import (
    BaseModel, NonEmptyString, NotRequired, ForUpdateMetaclass, Excluded, excluded_field, single_argument_args,
)
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
    "DiskSedUnlockArgs",
    "DiskSedUnlockResult",
    "DiskSedSetupDiskArgs",
    "DiskSedSetupDiskResult",
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
    """Logical unit number identifier or `null` if not applicable."""
    size: int | None
    """Total size of the disk in bytes. `null` if not available."""
    description: str
    """Human-readable description of the disk device."""
    transfermode: str
    """Data transfer mode and capabilities of the disk."""
    hddstandby: Literal["ALWAYS ON", "5", "10", "20", "30", "60", "120", "180", "240", "300", "330"]
    """Hard disk standby timer in minutes or `ALWAYS ON` to disable standby."""
    advpowermgmt: Literal["DISABLED", "1", "64", "127", "128", "192", "254"]
    """Advanced power management level or `DISABLED` to turn off power management."""
    expiretime: datetime | None
    """Expiration timestamp for disk data or `null` if not applicable."""
    model: str | None
    """Manufacturer model name/number of the disk. `null` if not available."""
    rotationrate: int | None
    """Disk rotation speed in RPM or `null` for SSDs and unknown devices."""
    type: str | None
    """Disk type classification or `null` if not determined."""
    zfs_guid: str | None
    """ZFS globally unique identifier for this disk or `null` if not used in ZFS."""
    bus: str
    """System bus type the disk is connected to."""
    devname: str = Field(examples=["/dev/sda"])
    """Device name in the operating system."""
    enclosure: DiskEntryEnclosure | None
    """Physical enclosure information or `null` if not in an enclosure."""
    pool: str | None
    """Name of the storage pool this disk belongs to. `null` if not part of any pool."""
    passwd: Secret[str] = NotRequired
    """Disk encryption password (masked for security)."""
    kmip_uid: str | None = NotRequired
    """KMIP (Key Management Interoperability Protocol) unique identifier or `null`."""
    sed: bool | None
    """Whether the disk is SED (Self-Encrypting Drive) capable. `null` if not yet determined."""
    sed_status: str | None = NotRequired
    """SED Status of the disk. `null` if not yet determined."""


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
    """Disk query parameters specifying which disks to return and options."""


class DiskDetailsResult(BaseModel):
    result: list | dict
    """Array of disk information or object with disk details depending on query options."""


class DiskGetUsedArgs(BaseModel):
    join_partitions: bool = False
    """Return all partitions currently written to disk.

    **NOTE: this is an expensive operation.**
    """


class DiskGetUsedResult(BaseModel):
    result: list
    """Array of disks that are currently in use by the system."""


class DiskTemperaturesArgs(BaseModel):
    name: list[str] = Field(default_factory=list)
    """
    List of names of disks to retrieve temperature information. Name should be in the form of "sda", "nvme0n1", etc.
    """
    include_thresholds: bool = False
    """Include the temperature thresholds as reported by the disk (i.e. the critical temp)."""


class DiskTemperaturesResult(BaseModel):
    result: dict
    """Object mapping disk names to their current temperature information."""


class DiskTemperatureAggArgs(BaseModel):
    names: list[str]
    """Array of disk names to retrieve temperature aggregates for."""
    days: int = 7
    """Number of days to aggregate temperature data over."""


class DiskTemperatureAggEntry(BaseModel):
    min_: int | float | None = Field(alias="min")
    """Minimum temperature recorded during the time period or `null`."""
    max_: int | float | None = Field(alias="max")
    """Maximum temperature recorded during the time period or `null`."""
    avg: int | float | None
    """Average temperature during the time period or `null`."""


class DiskTemperatureAggResult(BaseModel):
    result: dict[str, DiskTemperatureAggEntry]
    """Object mapping disk names to their aggregated temperature statistics."""


class DiskTemperatureAlertsArgs(BaseModel):
    names: list[str]
    """Array of disk names to check for temperature-related alerts."""


class DiskTemperatureAlertsResult(BaseModel):
    result: list[Alert]
    """Array of active temperature alerts for the specified disks."""


class DiskUpdateArgs(BaseModel):
    id: str
    """Disk identifier to update."""
    data: DiskUpdate
    """Updated disk configuration data."""


class DiskUpdateResult(BaseModel):
    result: DiskEntry
    """The updated disk configuration."""


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
    """Returns `null` when the disk wipe operation is successfully started."""


class DiskSedUnlockArgs(BaseModel):
    name: NonEmptyString
    """Name of disk to unlock."""
    password: Secret[NonEmptyString]
    """Password for disk to unlock."""
    new_password: Secret[NonEmptyString] = NotRequired
    """
    Optional password attribute to change the disk password if the disk 
    unlock is successful with the provided password.
    """


class DiskSedUnlockResult(BaseModel):
    result: bool
    """Returns true if the disk unlock was successful."""


@single_argument_args('disk_sed_setup')
class DiskSedSetupDiskArgs(BaseModel):
    name: NonEmptyString
    """Name of disk to setup."""
    password: Secret[NonEmptyString | None] = None
    """
    Password to use to setup the disk. If this is not set, first if a password on disk is set,
    it will be used else global configured SED password will be used.
    """


class DiskSedSetupDiskResult(BaseModel):
    result: bool
    """Returns true if the disk setup was successful."""
