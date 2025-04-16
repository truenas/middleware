from datetime import datetime

from pydantic import Field

from middlewared.api.base import BaseModel, single_argument_result


__all__ = [
    "SystemDebugArgs",
    "SystemDebugResult",
    "SystemHostIDArgs",
    "SystemHostIDResult",
    "SystemInfoArgs",
    "SystemInfoResult",
]


class SystemDebugArgs(BaseModel):
    pass


class SystemDebugResult(BaseModel):
    result: None


class SystemHostIDArgs(BaseModel):
    pass


class SystemHostIDResult(BaseModel):
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
    uptime: str
    uptime_seconds: float
    system_serial: str | None
    system_product: str | None
    system_product_version: str | None
    license: dict | None
    boottime: datetime
    datetime_: datetime = Field(alias="datetime")
    timezone: str
    system_manufacturer: str | None
    ecc_memory: bool
