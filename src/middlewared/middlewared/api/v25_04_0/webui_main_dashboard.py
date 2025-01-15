from datetime import datetime

from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString


class WebUIMainDashboardSysInfoArgs(BaseModel):
    pass


class SysInfoEntry(BaseModel):
    platform: NonEmptyString
    version: NonEmptyString
    codename: NonEmptyString
    license: dict
    system_serial: str
    hostname: NonEmptyString
    uptime_seconds: float
    datetime_: datetime = Field(alias="datetime")


class SysInfo(SysInfoEntry):
    remote_info: SysInfoEntry | None


class WebUIMainDashboardSysInfoResult(BaseModel):
    result: SysInfo
