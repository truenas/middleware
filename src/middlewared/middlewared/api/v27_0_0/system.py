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
    result: None = Field(description="Debug information collection completed successfully.")


class SystemHostIdArgs(BaseModel):
    pass


class SystemHostIdResult(BaseModel):
    result: str = Field(description="The system host identifier.")


class SystemInfoArgs(BaseModel):
    pass


@single_argument_result
class SystemInfoResult(BaseModel):
    version: str = Field(description="TrueNAS version.")
    buildtime: datetime = Field(description="TrueNAS build time.")
    hostname: str = Field(description="System host name.")
    physmem: int = Field(description="System physical memory in bytes.")
    model: str = Field(description="CPU model.")
    cores: int = Field(description="Number of CPU cores.")
    physical_cores: int = Field(description="Number of physical CPU cores.")
    loadavg: list = Field(description="System load averages over 1, 5, and 15 minute periods.")
    uptime: str = Field(description="Human-readable system uptime string.")
    uptime_seconds: float = Field(description="System uptime in seconds since boot.")
    system_serial: str | None = Field(description="System hardware serial number. `null` if not available.")
    system_product: str | None = Field(
        description="System product name from hardware manufacturer. `null` if not available.",
    )
    system_product_version: str | None = Field(
        description="System product version from hardware manufacturer. `null` if not available.",
    )
    license: dict | None = Field(description="System license information. `null` if no license is installed.")
    boottime: datetime = Field(description="System boot time.")
    datetime_: datetime = Field(alias="datetime", description="Current system date and time.")
    timezone: str = Field(description="System timezone identifier.")
    system_manufacturer: str | None = Field(
        description="System manufacturer name from hardware. `null` if not available.",
    )
    ecc_memory: bool = Field(description="Whether the system has ECC (Error Correcting Code) memory.")
