from typing import Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, LongString,
    single_argument_args,
)


__all__ = [
    'UPSEntry', 'UPSPortChoicesArgs', 'UPSPortChoicesResult', 'UPSDriverChoicesArgs',
    'UPSDriverChoicesResult', 'UPSUpdateArgs', 'UPSUpdateResult',
]


class UPSEntry(BaseModel):
    powerdown: bool
    rmonitor: bool
    id: int
    nocommwarntime: int | None
    remoteport: int = Field(ge=1, le=65535)
    shutdowntimer: int
    hostsync: int = Field(ge=0)
    description: str
    driver: str
    extrausers: LongString
    identifier: NonEmptyString
    mode: Literal['MASTER', 'SLAVE']
    monpwd: str
    monuser: NonEmptyString
    options: LongString
    optionsupsd: LongString
    port: str
    remotehost: str
    shutdown: Literal['LOWBATT', 'BATT']
    shutdowncmd: str | None
    complete_identifier: str


@single_argument_args('ups_update')
class UPSUpdateArgs(UPSEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    complete_identifier: Excluded = excluded_field()
    monpwd: NonEmptyString


class UPSUpdateResult(BaseModel):
    result: UPSEntry


class UPSPortChoicesArgs(BaseModel):
    pass


class UPSPortChoicesResult(BaseModel):
    result: list[str]


class UPSDriverChoicesArgs(BaseModel):
    pass


class UPSDriverChoicesResult(BaseModel):
    result: dict[str, str]
