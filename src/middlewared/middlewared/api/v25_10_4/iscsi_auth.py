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
    """Unique identifier for the iSCSI authentication credential."""
    tag: int
    """Numeric tag used to associate this credential with iSCSI targets."""
    user: str
    """Username for iSCSI CHAP authentication."""
    secret: Secret[str]
    """Password/secret for iSCSI CHAP authentication."""
    peeruser: str = ''
    """Username for mutual CHAP authentication or empty string if not configured."""
    peersecret: Secret[str] = ''
    """Password/secret for mutual CHAP authentication or empty string if not configured."""
    discovery_auth: IscsiAuthType = 'NONE'
    """Authentication method for target discovery. If "CHAP_MUTUAL" is selected for target discovery, it is only \
    permitted for a single entry systemwide."""


class IscsiAuthCreate(iSCSITargetAuthCredentialEntry):
    id: Excluded = excluded_field()


class iSCSITargetAuthCredentialCreateArgs(BaseModel):
    data: IscsiAuthCreate
    """iSCSI authentication credential configuration data for creation."""


class iSCSITargetAuthCredentialCreateResult(BaseModel):
    result: iSCSITargetAuthCredentialEntry
    """The created iSCSI authentication credential."""


class IscsiAuthUpdate(IscsiAuthCreate, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetAuthCredentialUpdateArgs(BaseModel):
    id: int
    """ID of the iSCSI authentication credential to update."""
    data: IscsiAuthUpdate
    """Updated iSCSI authentication credential configuration data."""


class iSCSITargetAuthCredentialUpdateResult(BaseModel):
    result: iSCSITargetAuthCredentialEntry
    """The updated iSCSI authentication credential."""


class iSCSITargetAuthCredentialDeleteArgs(BaseModel):
    id: int
    """ID of the iSCSI authentication credential to delete."""


class iSCSITargetAuthCredentialDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the iSCSI authentication credential is successfully deleted."""
