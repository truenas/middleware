from typing import Literal

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, excluded_field

__all__ = [
    "iSCSITargetAuthorizedInitiatorEntry",
    "iSCSITargetAuthorizedInitiatorCreateArgs",
    "iSCSITargetAuthorizedInitiatorCreateResult",
    "iSCSITargetAuthorizedInitiatorUpdateArgs",
    "iSCSITargetAuthorizedInitiatorUpdateResult",
    "iSCSITargetAuthorizedInitiatorDeleteArgs",
    "iSCSITargetAuthorizedInitiatorDeleteResult",
]


class iSCSITargetAuthorizedInitiatorEntry(BaseModel):
    id: int
    initiators: list[str] = []
    comment: str = ''


class IscsiInitiatorCreate(iSCSITargetAuthorizedInitiatorEntry):
    id: Excluded = excluded_field()


class iSCSITargetAuthorizedInitiatorCreateArgs(BaseModel):
    iscsi_initiator_create: IscsiInitiatorCreate


class iSCSITargetAuthorizedInitiatorCreateResult(BaseModel):
    result: iSCSITargetAuthorizedInitiatorEntry


class IscsiInitiatorUpdate(iSCSITargetAuthorizedInitiatorEntry, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetAuthorizedInitiatorUpdateArgs(BaseModel):
    id: int
    iscsi_initiator_update: IscsiInitiatorUpdate


class iSCSITargetAuthorizedInitiatorUpdateResult(BaseModel):
    result: iSCSITargetAuthorizedInitiatorEntry


class iSCSITargetAuthorizedInitiatorDeleteArgs(BaseModel):
    id: int


class iSCSITargetAuthorizedInitiatorDeleteResult(BaseModel):
    result: Literal[True]
