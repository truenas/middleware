from typing import Literal

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, excluded_field

__all__ = [
    "IscsiTargetToExtentEntry",
    "IscsiTargetToExtentCreateArgs",
    "IscsiTargetToExtentCreateResult",
    "IscsiTargetToExtentUpdateArgs",
    "IscsiTargetToExtentUpdateResult",
    "IscsiTargetToExtentDeleteArgs",
    "IscsiTargetToExtentDeleteResult",
]


class IscsiTargetToExtentEntry(BaseModel):
    id: int
    target: int
    lunid: int
    extent: int


class IscsiTargetToExtentCreate(IscsiTargetToExtentEntry):
    id: Excluded = excluded_field()
    lunid: int | None = None
    defer: bool = False


class IscsiTargetToExtentCreateArgs(BaseModel):
    iscsi_target_to_extent_create: IscsiTargetToExtentCreate


class IscsiTargetToExtentCreateResult(BaseModel):
    result: IscsiTargetToExtentEntry


class IscsiTargetToExtentUpdate(IscsiTargetToExtentEntry, metaclass=ForUpdateMetaclass):
    defer: bool = False


class IscsiTargetToExtentUpdateArgs(BaseModel):
    id: int
    iscsi_target_to_extent_update: IscsiTargetToExtentUpdate


class IscsiTargetToExtentUpdateResult(BaseModel):
    result: IscsiTargetToExtentEntry


class IscsiTargetToExtentDeleteArgs(BaseModel):
    id: int
    force: bool = False
    defer: bool = False


class IscsiTargetToExtentDeleteResult(BaseModel):
    result: Literal[True]


class IscsiTargetToExtentRemoveArgs(BaseModel):
    name: str


class IscsiTargetToExtentRemoveResult(BaseModel):
    result: None
