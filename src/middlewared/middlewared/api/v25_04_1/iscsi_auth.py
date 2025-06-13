from typing import Literal

from pydantic import Secret

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, IscsiAuthType

__all__ = [
    "IscsiAuthEntry",
    "iSCSITargetAuthCredentialCreateArgs",
    "iSCSITargetAuthCredentialCreateResult",
    "iSCSITargetAuthCredentialUpdateArgs",
    "iSCSITargetAuthCredentialUpdateResult",
    "iSCSITargetAuthCredentialDeleteArgs",
    "iSCSITargetAuthCredentialDeleteResult",
]


class IscsiAuthEntry(BaseModel):
    id: int
    tag: int
    user: str
    secret: Secret[str]
    peeruser: str = ''
    peersecret: Secret[str] = ''
    discovery_auth: IscsiAuthType = 'NONE'


class IscsiAuthCreate(IscsiAuthEntry):
    id: Excluded = excluded_field()


class iSCSITargetAuthCredentialCreateArgs(BaseModel):
    data: IscsiAuthCreate


class iSCSITargetAuthCredentialCreateResult(BaseModel):
    result: IscsiAuthEntry


class IscsiAuthUpdate(IscsiAuthCreate, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetAuthCredentialUpdateArgs(BaseModel):
    id: int
    data: IscsiAuthUpdate


class iSCSITargetAuthCredentialUpdateResult(BaseModel):
    result: IscsiAuthEntry


class iSCSITargetAuthCredentialDeleteArgs(BaseModel):
    id: int


class iSCSITargetAuthCredentialDeleteResult(BaseModel):
    result: Literal[True]
