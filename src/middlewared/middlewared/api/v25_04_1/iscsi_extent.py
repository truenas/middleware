from typing import Annotated, Literal

from annotated_types import Ge, Le
from pydantic import Field, StringConstraints

from middlewared.api.base import (BaseModel, Excluded, ForUpdateMetaclass, IscsiExtentBlockSize, IscsiExtentRPM,
                                  IscsiExtentType, NonEmptyString, excluded_field)

__all__ = [
    "IscsiExtentEntry",
    "IscsiExtentCreateArgs",
    "IscsiExtentCreateResult",
    "IscsiExtentUpdateArgs",
    "IscsiExtentUpdateResult",
    "IscsiExtentDeleteArgs",
    "IscsiExtentDeleteResult",
    "IscsiExtentDiskChoicesArgs",
    "IscsiExtentDiskChoicesResult",
]


class IscsiExtentEntry(BaseModel):
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


class IscsiExtentCreate(IscsiExtentEntry):
    id: Excluded = excluded_field()
    naa: Excluded = excluded_field()
    vendor: Excluded = excluded_field()
    locked: Excluded = excluded_field()


class IscsiExtentCreateArgs(BaseModel):
    iscsi_extent_create: IscsiExtentCreate


class IscsiExtentCreateResult(BaseModel):
    result: IscsiExtentEntry


class IscsiExtentUpdate(IscsiExtentCreate, metaclass=ForUpdateMetaclass):
    pass


class IscsiExtentUpdateArgs(BaseModel):
    id: int
    iscsi_extent_update: IscsiExtentUpdate


class IscsiExtentUpdateResult(BaseModel):
    result: IscsiExtentEntry


class IscsiExtentDeleteArgs(BaseModel):
    id: int
    remove: bool = False
    force: bool = False


class IscsiExtentDeleteResult(BaseModel):
    result: Literal[True]


class IscsiExtentDiskChoicesArgs(BaseModel):
    pass


class IscsiExtentDiskChoicesResult(BaseModel):
    result: dict[str, str]
