from typing import Literal

from pydantic import Field

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
    id: int = Field(description="Unique identifier for the authorized initiator group.")
    initiators: list[str] = Field(
        default=[],
        description="Array of iSCSI Qualified Names (IQNs) or IP addresses of authorized initiators.",
    )
    comment: str = Field(default='', description="Optional comment describing the authorized initiator group.")


class IscsiInitiatorCreate(iSCSITargetAuthorizedInitiatorEntry):
    id: Excluded = excluded_field()


class iSCSITargetAuthorizedInitiatorCreateArgs(BaseModel):
    iscsi_initiator_create: IscsiInitiatorCreate = Field(
        description="Authorized initiator group configuration data for creation.",
    )


class iSCSITargetAuthorizedInitiatorCreateResult(BaseModel):
    result: iSCSITargetAuthorizedInitiatorEntry = Field(
        description="The created authorized initiator group configuration.",
    )


class IscsiInitiatorUpdate(iSCSITargetAuthorizedInitiatorEntry, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetAuthorizedInitiatorUpdateArgs(BaseModel):
    id: int = Field(description="ID of the authorized initiator group to update.")
    iscsi_initiator_update: IscsiInitiatorUpdate = Field(
        description="Updated authorized initiator group configuration data.",
    )


class iSCSITargetAuthorizedInitiatorUpdateResult(BaseModel):
    result: iSCSITargetAuthorizedInitiatorEntry = Field(
        description="The updated authorized initiator group configuration.",
    )


class iSCSITargetAuthorizedInitiatorDeleteArgs(BaseModel):
    id: int = Field(description="ID of the authorized initiator group to delete.")


class iSCSITargetAuthorizedInitiatorDeleteResult(BaseModel):
    result: Literal[True] = Field(
        description="Returns `true` when the authorized initiator group is successfully deleted.",
    )
