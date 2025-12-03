from typing import Annotated, Literal

from annotated_types import Ge, Le
from pydantic import Field, StringConstraints

from middlewared.api.base import (BaseModel, Excluded, ForUpdateMetaclass, IscsiExtentBlockSize, IscsiExtentRPM,
                                  IscsiExtentType, NonEmptyString, excluded_field)

__all__ = [
    "iSCSITargetExtentEntry",
    "iSCSITargetExtentCreateArgs",
    "iSCSITargetExtentCreateResult",
    "iSCSITargetExtentUpdateArgs",
    "iSCSITargetExtentUpdateResult",
    "iSCSITargetExtentDeleteArgs",
    "iSCSITargetExtentDeleteResult",
    "iSCSITargetExtentDiskChoicesArgs",
    "iSCSITargetExtentDiskChoicesResult",
]


class iSCSITargetExtentEntry(BaseModel):
    id: int
    name: Annotated[NonEmptyString, StringConstraints(max_length=64)]
    type: IscsiExtentType = 'DISK'
    disk: str | None = None
    serial: str | None = None
    path: str | None = None
    filesize: str | int = '0'
    blocksize: IscsiExtentBlockSize = 512
    pblocksize: bool = False
    avail_threshold: Annotated[int, Ge(1), Le(99)] | None = None
    comment: str = ''
    naa: str = Field(max_length=34)
    insecure_tpc: bool = True
    xen: bool = False
    rpm: IscsiExtentRPM = 'SSD'
    ro: bool = False
    enabled: bool = True
    vendor: str
    locked: bool | None


class IscsiExtentCreate(iSCSITargetExtentEntry):
    id: Excluded = excluded_field()
    naa: Excluded = excluded_field()
    vendor: Excluded = excluded_field()
    locked: Excluded = excluded_field()


class iSCSITargetExtentCreateArgs(BaseModel):
    iscsi_extent_create: IscsiExtentCreate


class iSCSITargetExtentCreateResult(BaseModel):
    result: iSCSITargetExtentEntry


class IscsiExtentUpdate(IscsiExtentCreate, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetExtentUpdateArgs(BaseModel):
    id: int
    iscsi_extent_update: IscsiExtentUpdate


class iSCSITargetExtentUpdateResult(BaseModel):
    result: iSCSITargetExtentEntry


class iSCSITargetExtentDeleteArgs(BaseModel):
    id: int
    remove: bool = False
    force: bool = False


class iSCSITargetExtentDeleteResult(BaseModel):
    result: Literal[True]


class iSCSITargetExtentDiskChoicesArgs(BaseModel):
    pass


class iSCSITargetExtentDiskChoicesResult(BaseModel):
    result: dict[str, str]
