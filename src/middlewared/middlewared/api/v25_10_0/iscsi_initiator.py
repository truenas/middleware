from typing import Literal

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, excluded_field

__all__ = [
    "IscsiInitiatorEntry",
    "iSCSITargetAuthorizedInitiatorCreateArgs",
    "iSCSITargetAuthorizedInitiatorCreateResult",
    "iSCSITargetAuthorizedInitiatorUpdateArgs",
    "iSCSITargetAuthorizedInitiatorUpdateResult",
    "iSCSITargetAuthorizedInitiatorDeleteArgs",
    "iSCSITargetAuthorizedInitiatorDeleteResult",
]


class IscsiInitiatorEntry(BaseModel):
    id: int
    initiators: list[str] = []
    comment: str = ''


class IscsiInitiatorCreate(IscsiInitiatorEntry):
    id: Excluded = excluded_field()


class iSCSITargetAuthorizedInitiatorCreateArgs(BaseModel):
    iscsi_initiator_create: IscsiInitiatorCreate


class iSCSITargetAuthorizedInitiatorCreateResult(BaseModel):
    result: IscsiInitiatorEntry


class IscsiInitiatorUpdate(IscsiInitiatorEntry, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetAuthorizedInitiatorUpdateArgs(BaseModel):
    id: int
    iscsi_initiator_update: IscsiInitiatorUpdate


class iSCSITargetAuthorizedInitiatorUpdateResult(BaseModel):
    result: IscsiInitiatorEntry


class iSCSITargetAuthorizedInitiatorDeleteArgs(BaseModel):
    id: int


class iSCSITargetAuthorizedInitiatorDeleteResult(BaseModel):
    result: Literal[True]
