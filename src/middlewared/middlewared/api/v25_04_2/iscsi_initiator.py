from typing import Literal

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, excluded_field

__all__ = [
    "IscsiInitiatorEntry",
    "IscsiInitiatorCreateArgs",
    "IscsiInitiatorCreateResult",
    "IscsiInitiatorUpdateArgs",
    "IscsiInitiatorUpdateResult",
    "IscsiInitiatorDeleteArgs",
    "IscsiInitiatorDeleteResult",
]


class IscsiInitiatorEntry(BaseModel):
    id: int
    initiators: list[str] = []
    comment: str = ''


class IscsiInitiatorCreate(IscsiInitiatorEntry):
    id: Excluded = excluded_field()


class IscsiInitiatorCreateArgs(BaseModel):
    iscsi_initiator_create: IscsiInitiatorCreate


class IscsiInitiatorCreateResult(BaseModel):
    result: IscsiInitiatorEntry


class IscsiInitiatorUpdate(IscsiInitiatorEntry, metaclass=ForUpdateMetaclass):
    pass


class IscsiInitiatorUpdateArgs(BaseModel):
    id: int
    iscsi_initiator_update: IscsiInitiatorUpdate


class IscsiInitiatorUpdateResult(BaseModel):
    result: IscsiInitiatorEntry


class IscsiInitiatorDeleteArgs(BaseModel):
    id: int


class IscsiInitiatorDeleteResult(BaseModel):
    result: Literal[True]
