from typing import Literal

from pydantic import Secret

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, IscsiAuthType

__all__ = [
    "iSCSITargetAuthCredentialEntry",
    "iSCSITargetAuthCredentialCreateArgs",
    "iSCSITargetAuthCredentialCreateResult",
    "iSCSITargetAuthCredentialUpdateArgs",
    "iSCSITargetAuthCredentialUpdateResult",
    "iSCSITargetAuthCredentialDeleteArgs",
    "iSCSITargetAuthCredentialDeleteResult",
]


class iSCSITargetAuthCredentialEntry(BaseModel):
    id: int
    tag: int
    user: str
    secret: Secret[str]
    peeruser: str = ''
    peersecret: Secret[str] = ''
    discovery_auth: IscsiAuthType = 'NONE'


class IscsiAuthCreate(iSCSITargetAuthCredentialEntry):
    id: Excluded = excluded_field()


class iSCSITargetAuthCredentialCreateArgs(BaseModel):
    data: IscsiAuthCreate


class iSCSITargetAuthCredentialCreateResult(BaseModel):
    result: iSCSITargetAuthCredentialEntry


class IscsiAuthUpdate(IscsiAuthCreate, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetAuthCredentialUpdateArgs(BaseModel):
    id: int
    data: IscsiAuthUpdate


class iSCSITargetAuthCredentialUpdateResult(BaseModel):
    result: iSCSITargetAuthCredentialEntry


class iSCSITargetAuthCredentialDeleteArgs(BaseModel):
    id: int


class iSCSITargetAuthCredentialDeleteResult(BaseModel):
    result: Literal[True]
