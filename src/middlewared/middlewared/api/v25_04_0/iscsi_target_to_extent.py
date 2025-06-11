from typing import Literal

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, excluded_field

__all__ = [
    "IscsiTargetToExtentEntry",
    "iSCSITargetToExtentCreateArgs",
    "iSCSITargetToExtentCreateResult",
    "iSCSITargetToExtentUpdateArgs",
    "iSCSITargetToExtentUpdateResult",
    "iSCSITargetToExtentDeleteArgs",
    "iSCSITargetToExtentDeleteResult",
]


class IscsiTargetToExtentEntry(BaseModel):
    id: int
    target: int
    lunid: int
    extent: int


class IscsiTargetToExtentCreate(IscsiTargetToExtentEntry):
    id: Excluded = excluded_field()
    lunid: int | None = None


class iSCSITargetToExtentCreateArgs(BaseModel):
    iscsi_target_to_extent_create: IscsiTargetToExtentCreate


class iSCSITargetToExtentCreateResult(BaseModel):
    result: IscsiTargetToExtentEntry


class IscsiTargetToExtentUpdate(IscsiTargetToExtentEntry, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetToExtentUpdateArgs(BaseModel):
    id: int
    iscsi_target_to_extent_update: IscsiTargetToExtentUpdate


class iSCSITargetToExtentUpdateResult(BaseModel):
    result: IscsiTargetToExtentEntry


class iSCSITargetToExtentDeleteArgs(BaseModel):
    id: int
    force: bool = False


class iSCSITargetToExtentDeleteResult(BaseModel):
    result: Literal[True]


class IscsiTargetToExtentRemoveArgs(BaseModel):
    name: str


class IscsiTargetToExtentRemoveResult(BaseModel):
    result: None
