from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from middlewared.api.base import (
    BaseModel, Excluded, ForUpdateMetaclass, IscsiExtentBlockSize,
    IscsiExtentRPM, IscsiExtentType, NonEmptyString, excluded_field
)

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
    """Unique identifier for the iSCSI extent."""
    name: Annotated[NonEmptyString, StringConstraints(max_length=64)]
    """Name of the iSCSI extent."""
    type: IscsiExtentType = 'DISK'
    """Type of the extent storage backend."""
    disk: str | None = None
    """Disk device to use for the extent or `null` if using a file."""
    serial: str | None = None
    """Serial number for the extent or `null` to auto-generate."""
    path: str | None = None
    """File path for file-based extents or `null` if using a disk."""
    filesize: str | int = '0'
    """Size of the file-based extent in bytes."""
    blocksize: IscsiExtentBlockSize = 512
    """Block size for the extent in bytes."""
    pblocksize: bool = False
    """Whether to use physical block size reporting."""
    avail_threshold: Annotated[int, Field(ge=1, le=99)] | None = None
    """Available space threshold percentage or `null` to disable."""
    comment: str = ''
    """Optional comment describing the extent."""
    naa: str = Field(max_length=34)
    """Network Address Authority (NAA) identifier for the extent."""
    insecure_tpc: bool = True
    """Whether to enable insecure Third Party Copy (TPC) operations."""
    xen: bool = False
    """Whether to enable Xen compatibility mode."""
    rpm: IscsiExtentRPM = 'SSD'
    """Reported RPM type for the extent."""
    ro: bool = False
    """Whether the extent is read-only."""
    enabled: bool = True
    """Whether the extent is enabled and available for use."""
    vendor: str
    """Vendor string reported by the extent."""
    product_id: Annotated[NonEmptyString, StringConstraints(max_length=16)] | None = None
    """Product ID string for the extent or `null` for default."""
    locked: bool | None
    """ Read-only value indicating whether the iscsi extent is located on a locked dataset.

    - `true`: The extent is in a locked dataset.
    - `false`: The extent is not in a locked dataset.
    - `null`: Lock status is not available because path locking information was not requested.
    """


class IscsiExtentCreate(iSCSITargetExtentEntry):
    id: Excluded = excluded_field()
    naa: Excluded = excluded_field()
    vendor: Excluded = excluded_field()
    locked: Excluded = excluded_field()


class iSCSITargetExtentCreateArgs(BaseModel):
    iscsi_extent_create: IscsiExtentCreate
    """iSCSI extent configuration data for creation."""


class iSCSITargetExtentCreateResult(BaseModel):
    result: iSCSITargetExtentEntry
    """The created iSCSI extent configuration."""


class IscsiExtentUpdate(IscsiExtentCreate, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetExtentUpdateArgs(BaseModel):
    id: int
    """ID of the iSCSI extent to update."""
    iscsi_extent_update: IscsiExtentUpdate
    """Updated iSCSI extent configuration data."""


class iSCSITargetExtentUpdateResult(BaseModel):
    result: iSCSITargetExtentEntry
    """The updated iSCSI extent configuration."""


class iSCSITargetExtentDeleteArgs(BaseModel):
    id: int
    """ID of the iSCSI extent to delete."""
    remove: bool = False
    """Whether to remove the underlying file for file-based extents."""
    force: bool = False
    """Whether to force deletion even if the extent is in use."""


class iSCSITargetExtentDeleteResult(BaseModel):
    result: Literal[True]
    """Returns `true` when the iSCSI extent is successfully deleted."""


class iSCSITargetExtentDiskChoicesArgs(BaseModel):
    pass


class iSCSITargetExtentDiskChoicesResult(BaseModel):
    result: dict[str, str]
    """Object mapping disk identifiers to their display names."""
