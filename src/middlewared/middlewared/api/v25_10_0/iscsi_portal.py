from typing import Literal

from pydantic import IPvAnyAddress, field_validator

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString

__all__ = [
    "IscsiPortalEntry",
    "IscsiPortalListenIPChoicesArgs",
    "IscsiPortalListenIPChoicesResult",
    "IscsiPortalCreateArgs",
    "IscsiPortalCreateResult",
    "IscsiPortalUpdateArgs",
    "IscsiPortalUpdateResult",
    "IscsiPortalDeleteArgs",
    "IscsiPortalDeleteResult",
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


class IscsiPortalEntry(BaseModel):
    id: int
    listen: list[IscsiPortalIPInfo]
    tag: int
    comment: str = ''


class IscsiPortalListenIPChoicesArgs(BaseModel):
    pass


class IscsiPortalListenIPChoicesResult(BaseModel):
    result: dict[str, str]


class IscsiPortalCreate(IscsiPortalEntry):
    id: Excluded = excluded_field()
    tag: Excluded = excluded_field()
    listen: list[IscsiPortalIP]


class IscsiPortalCreateArgs(BaseModel):
    iscsi_portal_create: IscsiPortalCreate


class IscsiPortalCreateResult(BaseModel):
    result: IscsiPortalEntry


class IscsiPortalUpdate(IscsiPortalCreate, metaclass=ForUpdateMetaclass):
    pass


class IscsiPortalUpdateArgs(BaseModel):
    id: int
    iscsi_portal_update: IscsiPortalUpdate


class IscsiPortalUpdateResult(BaseModel):
    result: IscsiPortalEntry


class IscsiPortalDeleteArgs(BaseModel):
    id: int


class IscsiPortalDeleteResult(BaseModel):
    result: Literal[True]
