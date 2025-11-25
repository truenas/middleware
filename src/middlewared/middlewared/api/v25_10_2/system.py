from datetime import datetime

from pydantic import Field

from middlewared.api.base import BaseModel, single_argument_result


__all__ = [
    "SystemDebugArgs",
    "SystemDebugResult",
    "SystemHostIdArgs",
    "SystemHostIdResult",
    "SystemInfoArgs",
    "SystemInfoResult",
]


class SystemDebugArgs(BaseModel):
    pass


class SystemDebugResult(BaseModel):
    result: None
    """Debug information collection completed successfully."""


class SystemHostIdArgs(BaseModel):
    pass


class SystemHostIdResult(BaseModel):
    result: str
    """The system host identifier."""


class SystemInfoArgs(BaseModel):
    pass


@single_argument_result
class SystemInfoResult(BaseModel):
    version: str
    """TrueNAS version."""
    buildtime: datetime
    """TrueNAS build time."""
    hostname: str
    """System host name."""
    physmem: int
    """System physical memory in bytes."""
    model: str
    """CPU model."""
    cores: int
    """Number of CPU cores."""
    physical_cores: int
    """Number of physical CPU cores."""
    loadavg: list
    """System load averages over 1, 5, and 15 minute periods."""
    uptime: str
    """Human-readable system uptime string."""
    uptime_seconds: float
    """System uptime in seconds since boot."""
    system_serial: str | None
    """System hardware serial number. `null` if not available."""
    system_product: str | None
    """System product name from hardware manufacturer. `null` if not available."""
    system_product_version: str | None
    """System product version from hardware manufacturer. `null` if not available."""
    license: dict | None
    """System license information. `null` if no license is installed."""
    boottime: datetime
    """System boot time."""
    datetime_: datetime = Field(alias="datetime")
    """Current system date and time."""
    timezone: str
    """System timezone identifier."""
    system_manufacturer: str | None
    """System manufacturer name from hardware. `null` if not available."""
    ecc_memory: bool
    """Whether the system has ECC (Error Correcting Code) memory."""
