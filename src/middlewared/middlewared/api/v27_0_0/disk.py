from datetime import datetime
from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    NonEmptyString,
    NotRequired,
    excluded_field,
    single_argument_args,
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
    "DiskUnlockSedArgs",
    "DiskUnlockSedResult",
    "DiskSetupSedArgs",
    "DiskSetupSedResult",
    "DiskResetSedArgs",
    "DiskResetSedResult",
    "DiskQueryAddedEvent",
    "DiskQueryChangedEvent",
    "DiskQueryRemovedEvent",
)


class DiskEntryEnclosure(BaseModel):
    number: int = Field(description="Enclosure number where the disk is located.")
    slot: int = Field(description="Physical slot position within the enclosure.")


class DiskEntry(BaseModel):
    identifier: str = Field(description="Unique identifier for the disk device.")
    name: str = Field(description="System name of the disk device.")
    subsystem: str = Field(examples=["SCSI", "ATA"], description="Storage subsystem type.")
    number: int = Field(description="Numeric identifier assigned to the disk.")
    serial: str = Field(description="Manufacturer serial number of the disk.")
    lunid: str | None = Field(description="Logical unit number identifier or `null` if not applicable.")
    size: int | None = Field(description="Total size of the disk in bytes. `null` if not available.")
    description: str = Field(description="Human-readable description of the disk device.")
    transfermode: str = Field(description="Data transfer mode and capabilities of the disk.")
    hddstandby: Literal["ALWAYS ON", "5", "10", "20", "30", "60", "120", "180", "240", "300", "330"] = Field(
        description="Hard disk standby timer in minutes or `ALWAYS ON` to disable standby.",
    )
    advpowermgmt: Literal["DISABLED", "1", "64", "127", "128", "192", "254"] = Field(
        description="Advanced power management level or `DISABLED` to turn off power management.",
    )
    expiretime: datetime | None = Field(description="Expiration timestamp for disk data or `null` if not applicable.")
    model: str | None = Field(description="Manufacturer model name/number of the disk. `null` if not available.")
    rotationrate: int | None = Field(description="Disk rotation speed in RPM or `null` for SSDs and unknown devices.")
    type: str | None = Field(description="Disk type classification or `null` if not determined.")
    zfs_guid: str | None = Field(
        description="ZFS globally unique identifier for this disk or `null` if not used in ZFS.",
    )
    bus: str = Field(description="System bus type the disk is connected to.")
    devname: str = Field(examples=["/dev/sda"], description="Device name in the operating system.")
    enclosure: DiskEntryEnclosure | None = Field(
        description="Physical enclosure information or `null` if not in an enclosure.",
    )
    pool: str | None = Field(
        description="Name of the storage pool this disk belongs to. `null` if not part of any pool.",
    )
    passwd: Secret[str] = Field(default=NotRequired, description="Disk encryption password (masked for security).")
    kmip_uid: str | None = Field(
        default=NotRequired,
        description="KMIP (Key Management Interoperability Protocol) unique identifier or `null`.",
    )
    sed: bool | None = Field(
        description="Whether the disk is SED (Self-Encrypting Drive) capable. `null` if not yet determined.",
    )
    sed_status: str | None = Field(
        default=NotRequired,
        description="SED Status of the disk. `null` if not yet determined.",
    )


class DiskDetails(BaseModel):
    join_partitions: bool = Field(
        default=False,
        description=(
            "Return all partitions currently written to disk.\n"
            "\n"
            "**NOTE: This is an expensive operation.**"
        ),
    )
    type: Literal["USED", "UNUSED", "BOTH"] = Field(
        default="BOTH",
        description=(
            "* `USED`: Only disks that are IN USE will be returned.\n"
            "* `UNUSED`: Only disks that are NOT IN USE are returned.\n"
            "* `BOTH`: Used and unused disks will be returned."
        ),
    )


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
    data: DiskDetails = Field(
        default_factory=DiskDetails,
        description="Disk query parameters specifying which disks to return and options.",
    )


class DiskDetailsResult(BaseModel):
    result: list | dict = Field(
        description="Array of disk information or object with disk details depending on query options.",
    )


class DiskGetUsedArgs(BaseModel):
    join_partitions: bool = Field(
        default=False,
        description=(
            "Return all partitions currently written to disk.\n"
            "\n"
            "**NOTE: this is an expensive operation.**"
        ),
    )


class DiskGetUsedResult(BaseModel):
    result: list = Field(description="Array of disks that are currently in use by the system.")


class DiskTemperaturesArgs(BaseModel):
    name: list[str] = Field(
        default_factory=list,
        description=(
            "List of names of disks to retrieve temperature information. Name should be in the form of \"sda\", "
            "\"nvme0n1\", etc."
        ),
    )
    include_thresholds: bool = Field(
        default=False,
        description="Include the temperature thresholds as reported by the disk (i.e. the critical temp).",
    )


class DiskTemperaturesResult(BaseModel):
    result: dict = Field(description="Object mapping disk names to their current temperature information.")


class DiskTemperatureAggArgs(BaseModel):
    names: list[str] = Field(description="Array of disk names to retrieve temperature aggregates for.")
    days: int = Field(default=7, description="Number of days to aggregate temperature data over.")


class DiskTemperatureAggEntry(BaseModel):
    min_: int | float | None = Field(
        alias="min",
        description="Minimum temperature recorded during the time period or `null`.",
    )
    max_: int | float | None = Field(
        alias="max",
        description="Maximum temperature recorded during the time period or `null`.",
    )
    avg: int | float | None = Field(description="Average temperature during the time period or `null`.")


class DiskTemperatureAggResult(BaseModel):
    result: dict[str, DiskTemperatureAggEntry] = Field(
        description="Object mapping disk names to their aggregated temperature statistics.",
    )


class DiskTemperatureAlertsArgs(BaseModel):
    names: list[str] = Field(description="Array of disk names to check for temperature-related alerts.")


class DiskTemperatureAlertsResult(BaseModel):
    result: list[Alert] = Field(description="Array of active temperature alerts for the specified disks.")


class DiskUpdateArgs(BaseModel):
    id: str = Field(description="Disk identifier to update.")
    data: DiskUpdate = Field(description="Updated disk configuration data.")


class DiskUpdateResult(BaseModel):
    result: DiskEntry = Field(description="The updated disk configuration.")


class DiskWipeArgs(BaseModel):
    dev: NonEmptyString = Field(
        description="The device to perform the disk wipe operation on. May be passed as /dev/sda or just sda.",
    )
    mode: Literal["QUICK", "FULL", "FULL_RANDOM"] = Field(
        description=(
            "* QUICK: Write zeros to the first and last 32MB of device.\n"
            "* FULL: Write whole disk with zeros.\n"
            "* FULL_RANDOM: Write whole disk with random bytes."
        ),
    )
    synccache: bool = Field(default=True, description="Synchronize the device with the database.")


class DiskWipeResult(BaseModel):
    result: None = Field(description="Returns `null` when the disk wipe operation is successfully started.")


@single_argument_args('disk_sed_unlock')
class DiskUnlockSedArgs(BaseModel):
    name: NonEmptyString = Field(description="Name of disk to unlock.")
    password: Secret[NonEmptyString | None] = Field(default=None, description="Password for disk to unlock.")


class DiskUnlockSedResult(BaseModel):
    result: Literal[True] = Field(description="Returns true if the disk unlock was successful.")


@single_argument_args('disk_sed_setup')
class DiskSetupSedArgs(BaseModel):
    name: NonEmptyString = Field(description="Name of disk to setup.")
    password: Secret[NonEmptyString | None] = Field(
        default=None,
        description=(
            "Password to use to setup the disk. If this is not set, first if a password on disk is set, it will be used"
            " else global configured SED password will be used."
        ),
    )


class DiskSetupSedResult(BaseModel):
    result: Literal[True] = Field(description="Returns true if the disk setup was successful.")


@single_argument_args('disk_sed_reset')
class DiskResetSedArgs(BaseModel):
    name: NonEmptyString = Field(description="Name of disk to reset.")
    psid: NonEmptyString = Field(description="PID of disk to reset.")


class DiskResetSedResult(BaseModel):
    result: Literal[True] = Field(description="Returns true if the disk reset was successful.")


class DiskQueryAddedEvent(BaseModel):
    id: str = Field(description="Disk identifier.")
    fields: DiskEntry = Field(description="Event fields.")


class DiskQueryChangedEvent(BaseModel):
    id: str = Field(description="Disk identifier.")
    fields: DiskEntry = Field(description="Event fields.")


class DiskQueryRemovedEvent(BaseModel):
    id: str = Field(description="Disk identifier.")
