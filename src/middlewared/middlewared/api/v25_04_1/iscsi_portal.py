from typing import Literal

from pydantic import IPvAnyAddress, field_validator

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString

__all__ = [
    "ISCSIPortalEntry",
    "ISCSIPortalListenIpChoicesArgs",
    "ISCSIPortalListenIpChoicesResult",
    "ISCSIPortalCreateArgs",
    "ISCSIPortalCreateResult",
    "ISCSIPortalUpdateArgs",
    "ISCSIPortalUpdateResult",
    "ISCSIPortalDeleteArgs",
    "ISCSIPortalDeleteResult",
]


class IscsiPortalIP(BaseModel):
    ip: NonEmptyString

    @field_validator('ip')
    @classmethod
    def check_ip(cls, v):
        IPvAnyAddress(v)
        return v


class IscsiPortalIPInfo(IscsiPortalIP):
    port: int


class ISCSIPortalEntry(BaseModel):
    id: int
    listen: list[IscsiPortalIPInfo]
    tag: int
    comment: str = ''


class ISCSIPortalListenIpChoicesArgs(BaseModel):
    pass


class ISCSIPortalListenIpChoicesResult(BaseModel):
    result: dict[str, str]


class IscsiPortalCreate(ISCSIPortalEntry):
    id: Excluded = excluded_field()
    tag: Excluded = excluded_field()
    listen: list[IscsiPortalIP]


class ISCSIPortalCreateArgs(BaseModel):
    iscsi_portal_create: IscsiPortalCreate


class ISCSIPortalCreateResult(BaseModel):
    result: ISCSIPortalEntry


class IscsiPortalUpdate(IscsiPortalCreate, metaclass=ForUpdateMetaclass):
    pass


class ISCSIPortalUpdateArgs(BaseModel):
    id: int
    iscsi_portal_update: IscsiPortalUpdate


class ISCSIPortalUpdateResult(BaseModel):
    result: ISCSIPortalEntry


class ISCSIPortalDeleteArgs(BaseModel):
    id: int


class ISCSIPortalDeleteResult(BaseModel):
    result: Literal[True]
