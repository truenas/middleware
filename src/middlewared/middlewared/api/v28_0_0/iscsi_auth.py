from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, IscsiAuthType, excluded_field

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
    id: int = Field(description="Unique identifier for the iSCSI authentication credential.")
    tag: int = Field(
        description=(
            "Numeric tag used to associate this credential with iSCSI targets. Must be unique among "
            "iSCSI Authorized Accesses."
        ),
    )
    user: str = Field(description="Username for iSCSI CHAP authentication.")
    secret: Secret[str] = Field(
        description="Password/secret for iSCSI CHAP authentication. Must be 12-16 characters.",
    )
    peeruser: str = Field(
        default='',
        description="Username for mutual CHAP authentication or empty string if not configured.",
    )
    peersecret: Secret[str] = Field(
        default='',
        description=(
            "Password/secret for mutual CHAP authentication, or empty string if not configured. Must be 12-16 "
            "characters when set and must differ from `secret`."
        ),
    )
    discovery_auth: IscsiAuthType = Field(
        default='NONE',
        description=(
            "Authentication method for target discovery. If \"CHAP_MUTUAL\" is selected for target discovery, it is "
            "only permitted for a single entry systemwide."
        ),
    )


class IscsiAuthCreate(iSCSITargetAuthCredentialEntry):
    id: Excluded = excluded_field()


class iSCSITargetAuthCredentialCreateArgs(BaseModel):
    data: IscsiAuthCreate = Field(description="iSCSI authentication credential configuration data for creation.")


class iSCSITargetAuthCredentialCreateResult(BaseModel):
    result: iSCSITargetAuthCredentialEntry = Field(description="The created iSCSI authentication credential.")


class IscsiAuthUpdate(IscsiAuthCreate, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetAuthCredentialUpdateArgs(BaseModel):
    id: int = Field(description="ID of the iSCSI authentication credential to update.")
    data: IscsiAuthUpdate = Field(description="Updated iSCSI authentication credential configuration data.")


class iSCSITargetAuthCredentialUpdateResult(BaseModel):
    result: iSCSITargetAuthCredentialEntry = Field(description="The updated iSCSI authentication credential.")


class iSCSITargetAuthCredentialDeleteArgs(BaseModel):
    id: int = Field(description="ID of the iSCSI authentication credential to delete.")


class iSCSITargetAuthCredentialDeleteResult(BaseModel):
    result: Literal[True] = Field(
        description="Returns `true` when the iSCSI authentication credential is successfully deleted.",
    )
