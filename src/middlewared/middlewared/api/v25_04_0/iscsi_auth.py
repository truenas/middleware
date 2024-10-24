from typing import Literal

from pydantic import Secret

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass

__all__ = [
    "IscsiAuthCreateArgs", "IscsiAuthCreateResult",
    "IscsiAuthUpdateArgs", "IscsiAuthUpdateResult",
    "IscsiAuthDeleteArgs", "IscsiAuthDeleteResult",
]


class IscsiAuthEntry(BaseModel):
    id: int
    tag: int
    user: str
    secret: Secret[str]
    peeruser: str = ''
    peersecret: Secret[str] = ''


class IscsiAuthCreate(IscsiAuthEntry):
    id: Excluded = excluded_field()


class IscsiAuthCreateArgs(BaseModel):
    data: IscsiAuthCreate


class IscsiAuthCreateResult(BaseModel):
    result: IscsiAuthEntry


class IscsiAuthUpdate(IscsiAuthCreate, metaclass=ForUpdateMetaclass):
    pass


class IscsiAuthUpdateArgs(BaseModel):
    id: int
    data: IscsiAuthUpdate


class IscsiAuthUpdateResult(BaseModel):
    result: IscsiAuthEntry


class IscsiAuthDeleteArgs(BaseModel):
    id: int


class IscsiAuthDeleteResult(BaseModel):
    result: Literal[True]
