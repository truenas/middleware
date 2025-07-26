from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from middlewared.api.base import (
    BaseModel, Excluded, ForUpdateMetaclass, IscsiExtentBlockSize,
    IscsiExtentRPM, IscsiExtentType, NonEmptyString, excluded_field
)

__all__ = [
    "IscsiExtentEntry",
    "iSCSITargetExtentCreateArgs",
    "iSCSITargetExtentCreateResult",
    "iSCSITargetExtentUpdateArgs",
    "iSCSITargetExtentUpdateResult",
    "iSCSITargetExtentDeleteArgs",
    "iSCSITargetExtentDeleteResult",
    "iSCSITargetExtentDiskChoicesArgs",
    "iSCSITargetExtentDiskChoicesResult",
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
    avail_threshold: Annotated[int, Field(ge=1, le=99)] | None = None
    comment: str = ''
    naa: str = Field(max_length=34)
    insecure_tpc: bool = True
    xen: bool = False
    rpm: IscsiExtentRPM = 'SSD'
    ro: bool = False
    enabled: bool = True
    vendor: str
    product_id: Annotated[NonEmptyString, StringConstraints(max_length=16)] | None = None
    locked: bool | None
    """ Read-only value indicating whether the iscsi extent is located on a locked dataset.

    Returns:
        - True: The extent is in a locked dataset.
        - False: The extent is not in a locked dataset.
        - None: Lock status is not available because path locking information was not requested.
    """


class IscsiExtentCreate(IscsiExtentEntry):
    id: Excluded = excluded_field()
    naa: Excluded = excluded_field()
    vendor: Excluded = excluded_field()
    locked: Excluded = excluded_field()
    defer: bool = False


class iSCSITargetExtentCreateArgs(BaseModel):
    iscsi_extent_create: IscsiExtentCreate


class iSCSITargetExtentCreateResult(BaseModel):
    result: IscsiExtentEntry


class IscsiExtentUpdate(IscsiExtentCreate, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetExtentUpdateArgs(BaseModel):
    id: int
    iscsi_extent_update: IscsiExtentUpdate


class iSCSITargetExtentUpdateResult(BaseModel):
    result: IscsiExtentEntry


class iSCSITargetExtentDeleteArgs(BaseModel):
    id: int
    remove: bool = False
    force: bool = False
    defer: bool = False


class iSCSITargetExtentDeleteResult(BaseModel):
    result: Literal[True]


class iSCSITargetExtentDiskChoicesArgs(BaseModel):
    pass


class iSCSITargetExtentDiskChoicesResult(BaseModel):
    result: dict[str, str]
