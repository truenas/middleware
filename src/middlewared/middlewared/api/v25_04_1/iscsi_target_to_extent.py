from typing import Literal

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
    id: int
    target: int
    lunid: int
    extent: int


class IscsiTargetToExtentCreate(iSCSITargetToExtentEntry):
    id: Excluded = excluded_field()
    lunid: int | None = None


class iSCSITargetToExtentCreateArgs(BaseModel):
    iscsi_target_to_extent_create: IscsiTargetToExtentCreate


class iSCSITargetToExtentCreateResult(BaseModel):
    result: iSCSITargetToExtentEntry


class IscsiTargetToExtentUpdate(iSCSITargetToExtentEntry, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetToExtentUpdateArgs(BaseModel):
    id: int
    iscsi_target_to_extent_update: IscsiTargetToExtentUpdate


class iSCSITargetToExtentUpdateResult(BaseModel):
    result: iSCSITargetToExtentEntry


class iSCSITargetToExtentDeleteArgs(BaseModel):
    id: int
    force: bool = False


class iSCSITargetToExtentDeleteResult(BaseModel):
    result: Literal[True]


class IscsiTargetToExtentRemoveArgs(BaseModel):
    name: str


class IscsiTargetToExtentRemoveResult(BaseModel):
    result: None
