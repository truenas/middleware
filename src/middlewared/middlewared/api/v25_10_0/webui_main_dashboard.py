from datetime import datetime

from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString


__all__ = ["WebUIMainDashboardSysInfoArgs", "WebUIMainDashboardSysInfoResult",]


class WebUIMainDashboardSysInfoArgs(BaseModel):
    pass


class RemoteInfo(BaseModel):
    platform: NonEmptyString
    version: NonEmptyString
    codename: NonEmptyString
    license: dict | None
    system_serial: str
    hostname: NonEmptyString
    uptime_seconds: float
    datetime_: datetime = Field(alias="datetime")


class SysInfo(RemoteInfo):
    remote_info: RemoteInfo | None


class WebUIMainDashboardSysInfoResult(BaseModel):
    result: SysInfo
