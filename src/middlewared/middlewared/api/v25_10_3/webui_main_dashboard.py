from datetime import datetime

from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString


__all__ = ["WebUIMainDashboardSysInfoArgs", "WebUIMainDashboardSysInfoResult",]


class WebUIMainDashboardSysInfoArgs(BaseModel):
    pass


class RemoteInfo(BaseModel):
    platform: NonEmptyString
    """Platform type (e.g., 'FREENAS', 'TRUENAS-SCALE')."""
    version: NonEmptyString
    """Software version string."""
    codename: NonEmptyString
    """Release codename for this version."""
    license: dict | None
    """License information object. `null` if no license is installed."""
    system_serial: str
    """Hardware serial number of the system."""
    hostname: NonEmptyString
    """System hostname."""
    uptime_seconds: float
    """System uptime in seconds since last boot."""
    datetime_: datetime = Field(alias="datetime")
    """Current system date and time."""


class SysInfo(RemoteInfo):
    remote_info: RemoteInfo | None
    """Information about the remote system in HA configurations. `null` for standalone systems."""


class WebUIMainDashboardSysInfoResult(BaseModel):
    result: SysInfo
    """System information for the web UI main dashboard display."""
