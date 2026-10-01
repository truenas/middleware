from datetime import datetime

from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString

__all__ = ["WebUIMainDashboardSysInfoArgs", "WebUIMainDashboardSysInfoResult",]


class WebUIMainDashboardSysInfoArgs(BaseModel):
    pass


class RemoteInfo(BaseModel):
    platform: NonEmptyString = Field(description="Platform type (e.g., 'FREENAS', 'TRUENAS-SCALE').")
    version: NonEmptyString = Field(description="Software version string.")
    license: dict | None = Field(description="License information object. `null` if no license is installed.")
    system_serial: str = Field(description="Hardware serial number of the system.")
    hostname: NonEmptyString = Field(description="System hostname.")
    uptime_seconds: float = Field(description="System uptime in seconds since last boot.")
    datetime_: datetime = Field(alias="datetime", description="Current system date and time.")

    @classmethod
    def to_previous(cls, value):
        value["codename"] = "<DEPRECATED>"


class SysInfo(RemoteInfo):
    remote_info: RemoteInfo | None = Field(
        description="Information about the remote system in HA configurations. `null` for standalone systems.",
    )


class WebUIMainDashboardSysInfoResult(BaseModel):
    result: SysInfo = Field(description="System information for the web UI main dashboard display.")
