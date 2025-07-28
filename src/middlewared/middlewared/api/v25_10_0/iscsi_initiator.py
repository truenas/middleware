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
    """Unique identifier for the authorized initiator group."""
    initiators: list[str] = []
    """Array of iSCSI Qualified Names (IQNs) or IP addresses of authorized initiators."""
    comment: str = ''
    """Optional comment describing the authorized initiator group."""


class IscsiInitiatorCreate(IscsiInitiatorEntry):
    id: Excluded = excluded_field()


class iSCSITargetAuthorizedInitiatorCreateArgs(BaseModel):
    iscsi_initiator_create: IscsiInitiatorCreate
    """Authorized initiator group configuration data for creation."""


class iSCSITargetAuthorizedInitiatorCreateResult(BaseModel):
    result: IscsiInitiatorEntry
    """The created authorized initiator group configuration."""


class IscsiInitiatorUpdate(IscsiInitiatorEntry, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetAuthorizedInitiatorUpdateArgs(BaseModel):
    id: int
    """ID of the authorized initiator group to update."""
    iscsi_initiator_update: IscsiInitiatorUpdate
    """Updated authorized initiator group configuration data."""


class iSCSITargetAuthorizedInitiatorUpdateResult(BaseModel):
    result: IscsiInitiatorEntry
    """The updated authorized initiator group configuration."""


class iSCSITargetAuthorizedInitiatorDeleteArgs(BaseModel):
    id: int
    """ID of the authorized initiator group to delete."""


class iSCSITargetAuthorizedInitiatorDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the authorized initiator group is successfully deleted."""
