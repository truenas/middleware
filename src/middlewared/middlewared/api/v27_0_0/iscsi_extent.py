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
    id: int = Field(description="Unique identifier for the iSCSI extent.")
    name: Annotated[NonEmptyString, StringConstraints(max_length=64)] = Field(description="Name of the iSCSI extent.")
    type: IscsiExtentType = Field(default='DISK', description="Type of the extent storage backend.")
    disk: str | None = Field(default=None, description="Disk device to use for the extent or `null` if using a file.")
    serial: str | None = Field(default=None, description="Serial number for the extent or `null` to auto-generate.")
    path: str | None = Field(default=None, description="File path for file-based extents or `null` if using a disk.")
    dataset: str | None = Field(
        description=(
            "The ZFS dataset containing the file-based extent (e.g., 'tank/iscsi'). Returns `null` for non-FILE extent "
            "types (DISK, ZVOL) or if the FILE path cannot be resolved yet (encrypted dataset not unlocked, etc.). This"
            " is a read-only field automatically populated from \"path\"."
        ),
    )
    relative_path: str | None = Field(
        description=(
            "The path of the file-based extent relative to the dataset mountpoint (e.g., 'extents/lun0.img'). An empty "
            "string indicates the file is at the dataset root. Returns `null` for non-FILE types or if the path cannot "
            "be resolved yet. This is a read-only field automatically populated from \"path\"."
        ),
    )
    filesize: str | int = Field(default='0', description="Size of the file-based extent in bytes.")
    blocksize: IscsiExtentBlockSize = Field(default=512, description="Block size for the extent in bytes.")
    pblocksize: bool = Field(default=False, description="Whether to use physical block size reporting.")
    avail_threshold: Annotated[int, Field(ge=1, le=99)] | None = Field(
        default=None,
        description="Available space threshold percentage or `null` to disable.",
    )
    comment: str = Field(default='', description="Optional comment describing the extent.")
    naa: str = Field(max_length=34, description="Network Address Authority (NAA) identifier for the extent.")
    insecure_tpc: bool = Field(
        default=True,
        description="Whether to enable insecure Third Party Copy (TPC) operations.",
    )
    xen: bool = Field(default=False, description="Whether to enable Xen compatibility mode.")
    rpm: IscsiExtentRPM = Field(default='SSD', description="Reported RPM type for the extent.")
    ro: bool = Field(default=False, description="Whether the extent is read-only.")
    enabled: bool = Field(default=True, description="Whether the extent is enabled and available for use.")
    vendor: str = Field(description="Vendor string reported by the extent.")
    product_id: Annotated[NonEmptyString, StringConstraints(max_length=16)] | None = Field(
        default=None,
        description="Product ID string for the extent or `null` for default.",
    )
    locked: bool | None = Field(
        description=(
            "Read-only value indicating whether the iscsi extent is located on a locked dataset.\n"
            "\n"
            "- `true`: The extent is in a locked dataset.\n"
            "- `false`: The extent is not in a locked dataset.\n"
            "- `null`: Lock status is not available because path locking information was not requested."
        ),
    )


class IscsiExtentCreate(iSCSITargetExtentEntry):
    id: Excluded = excluded_field()
    naa: Excluded = excluded_field()
    vendor: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    relative_path: Excluded = excluded_field()
    locked: Excluded = excluded_field()


class iSCSITargetExtentCreateArgs(BaseModel):
    iscsi_extent_create: IscsiExtentCreate = Field(description="iSCSI extent configuration data for creation.")


class iSCSITargetExtentCreateResult(BaseModel):
    result: iSCSITargetExtentEntry = Field(description="The created iSCSI extent configuration.")


class IscsiExtentUpdate(IscsiExtentCreate, metaclass=ForUpdateMetaclass):
    pass


class iSCSITargetExtentUpdateArgs(BaseModel):
    id: int = Field(description="ID of the iSCSI extent to update.")
    iscsi_extent_update: IscsiExtentUpdate = Field(description="Updated iSCSI extent configuration data.")


class iSCSITargetExtentUpdateResult(BaseModel):
    result: iSCSITargetExtentEntry = Field(description="The updated iSCSI extent configuration.")


class iSCSITargetExtentDeleteArgs(BaseModel):
    id: int = Field(description="ID of the iSCSI extent to delete.")
    remove: bool = Field(default=False, description="Whether to remove the underlying file for file-based extents.")
    force: bool = Field(default=False, description="Whether to force deletion even if the extent is in use.")


class iSCSITargetExtentDeleteResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when the iSCSI extent is successfully deleted.")


class iSCSITargetExtentDiskChoicesArgs(BaseModel):
    pass


class iSCSITargetExtentDiskChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Object mapping disk identifiers to their display names.")
