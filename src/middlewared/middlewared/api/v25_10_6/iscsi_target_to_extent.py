from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, excluded_field

__all__ = [
    "iSCSITargetToExtentEntry",
    "iSCSITargetToExtentCreateArgs",
    "iSCSITargetToExtentCreateResult",
    "iSCSITargetToExtentUpdateArgs",
    "iSCSITargetToExtentUpdateResult",
    "iSCSITargetToExtentDeleteArgs",
    "iSCSITargetToExtentDeleteResult",
]


class iSCSITargetToExtentEntry(BaseModel):
    id: int = Field(description="Unique identifier for the target-to-extent association.")
    target: int = Field(description="ID of the iSCSI target to associate with the extent.")
    lunid: int = Field(description="Logical Unit Number (LUN) ID for presenting the extent to the target.")
    extent: int = Field(description="ID of the iSCSI extent to associate with the target.")


class IscsiTargetToExtentCreate(iSCSITargetToExtentEntry):
    id: Excluded = excluded_field()
    lunid: int | None = Field(
        default=None,
        description="LUN ID to assign or `null` to auto-assign the next available LUN.",
    )


class iSCSITargetToExtentCreateArgs(BaseModel):
    iscsi_target_to_extent_create: IscsiTargetToExtentCreate = Field(
        description="Target-to-extent association configuration data for creation.",
    )


class iSCSITargetToExtentCreateResult(BaseModel):
    result: iSCSITargetToExtentEntry = Field(description="The created target-to-extent association.")


class IscsiTargetToExtentUpdate(iSCSITargetToExtentEntry, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetToExtentUpdateArgs(BaseModel):
    id: int = Field(description="ID of the target-to-extent association to update.")
    iscsi_target_to_extent_update: IscsiTargetToExtentUpdate = Field(
        description="Updated target-to-extent association configuration data.",
    )


class iSCSITargetToExtentUpdateResult(BaseModel):
    result: iSCSITargetToExtentEntry = Field(description="The updated target-to-extent association.")


class iSCSITargetToExtentDeleteArgs(BaseModel):
    id: int = Field(description="ID of the target-to-extent association to delete.")
    force: bool = Field(default=False, description="Whether to force deletion even if the association is in use.")


class iSCSITargetToExtentDeleteResult(BaseModel):
    result: Literal[True] = Field(
        description="Returns `true` when the target-to-extent association is successfully deleted.",
    )


class IscsiTargetToExtentRemoveArgs(BaseModel):
    name: str = Field(description="Name of the target-to-extent association to remove.")


class IscsiTargetToExtentRemoveResult(BaseModel):
    result: None = Field(description="Returns `null` when the target-to-extent association is successfully removed.")
