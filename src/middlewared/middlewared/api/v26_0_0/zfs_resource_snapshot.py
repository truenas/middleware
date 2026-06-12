from typing import Literal

from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from middlewared.api.base import (
    BaseModel,
    NonEmptyString,
    NotRequired,
    UniqueList,
)

from .zfs_resource_crud import PropertyValue

__all__ = (
    "ZFSResourceSnapshotEntry",
    "ZFSResourceSnapshotPropertiesEntry",
    "ZFSResourceSnapshotQueryBase",
    "ZFSResourceSnapshotQuery",
    "ZFSResourceSnapshotQueryArgs",
    "ZFSResourceSnapshotQueryResult",
    "ZFSResourceSnapshotCountQuery",
    "ZFSResourceSnapshotCountArgs",
    "ZFSResourceSnapshotCountResult",
    "ZFSResourceSnapshotDestroyQuery",
    "ZFSResourceSnapshotDestroyArgs",
    "ZFSResourceSnapshotDestroyResult",
    "ZFSResourceSnapshotRenameQuery",
    "ZFSResourceSnapshotRenameArgs",
    "ZFSResourceSnapshotRenameResult",
    "ZFSResourceSnapshotCloneQuery",
    "ZFSResourceSnapshotCloneArgs",
    "ZFSResourceSnapshotCloneResult",
    "ZFSResourceSnapshotCreateQuery",
    "ZFSResourceSnapshotCreateArgs",
    "ZFSResourceSnapshotCreateResult",
    "ZFSResourceSnapshotHoldQuery",
    "ZFSResourceSnapshotHoldArgs",
    "ZFSResourceSnapshotHoldResult",
    "ZFSResourceSnapshotHoldsQuery",
    "ZFSResourceSnapshotHoldsArgs",
    "ZFSResourceSnapshotHoldsResult",
    "ZFSResourceSnapshotReleaseQuery",
    "ZFSResourceSnapshotReleaseArgs",
    "ZFSResourceSnapshotReleaseResult",
    "ZFSResourceSnapshotRollbackQuery",
    "ZFSResourceSnapshotRollbackArgs",
    "ZFSResourceSnapshotRollbackResult",
)


class ZFSResourceSnapshotPropertiesEntry(BaseModel):
    # Common properties (both filesystem and volume snapshots)
    type: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Type of ZFS dataset (filesystem, volume, etc).",
    )
    creation: PropertyValue = Field(default=NotRequired, description="(READ-ONLY): Timestamp when dataset was created.")
    used: PropertyValue = Field(default=NotRequired, description="(READ-ONLY): Space used by dataset and descendants.")
    referenced: PropertyValue = Field(default=NotRequired, description="(READ-ONLY): Space referenced by this dataset.")
    compressratio: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Property showing achieved compression ratio.",
    )
    createtxg: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Transaction group when dataset was created.",
    )
    guid: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Globally unique identifier for the dataset.",
    )
    primarycache: PropertyValue = Field(
        default=NotRequired,
        description="Controls primary cache usage (all, metadata, or none).",
    )
    secondarycache: PropertyValue = Field(
        default=NotRequired,
        description="Controls secondary cache usage (all, metadata, or none).",
    )
    objsetid: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Object set identifier for the dataset.",
    )
    mlslabel: PropertyValue = Field(default=NotRequired, description="Multi-level security label for the dataset.")
    refcompressratio: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Compression ratio for referenced data.",
    )
    written: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Space referenced since previous snapshot.",
    )
    logicalreferenced: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Logical space referenced by dataset.",
    )
    context: PropertyValue = Field(default=NotRequired, description="SELinux security context for the dataset.")
    fscontext: PropertyValue = Field(default=NotRequired, description="SELinux filesystem security context.")
    defcontext: PropertyValue = Field(
        default=NotRequired,
        description="SELinux default security context for new files.",
    )
    rootcontext: PropertyValue = Field(default=NotRequired, description="SELinux root directory security context.")
    encryption: PropertyValue = Field(
        default=NotRequired,
        description="Controls encryption cipher suite for the dataset.",
    )
    encryptionroot: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Property showing encryption root dataset.",
    )
    keystatus: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Encryption key status (available/unavailable).",
    )
    redact_snaps: PropertyValue = Field(default=NotRequired, description="(READ-ONLY): List of redaction snapshots.")
    prefetch: PropertyValue = Field(
        default=NotRequired,
        description="Controls prefetch behavior (all, metadata, or none).",
    )
    # Filesystem snapshot specific properties
    devices: PropertyValue = Field(default=NotRequired, description="Controls whether device files can be opened.")
    exec: PropertyValue = Field(
        default=NotRequired,
        description="Controls whether programs can be executed from filesystem.",
    )
    setuid: PropertyValue = Field(
        default=NotRequired,
        description="Controls setuid/setgid bit respect on executable files.",
    )
    xattr: PropertyValue = Field(
        default=NotRequired,
        description="Controls extended attribute behavior (on, off, sa, dir).",
    )
    version: PropertyValue = Field(default=NotRequired, description="(READ-ONLY): Filesystem version number.")
    utf8only: PropertyValue = Field(
        default=NotRequired,
        description="Controls whether only UTF-8 filenames are allowed.",
    )
    normalization: PropertyValue = Field(
        default=NotRequired,
        description="Unicode normalization property for filenames.",
    )
    casesensitivity: PropertyValue = Field(
        default=NotRequired,
        description="Determines filename matching algorithm sensitivity.",
    )
    nbmand: PropertyValue = Field(default=NotRequired, description="Controls non-blocking mandatory locking behavior.")
    acltype: PropertyValue = Field(default=NotRequired, description="Specifies type of ACL to use (off, nfsv4, posix).")
    defaultuserquota: PropertyValue = Field(default=NotRequired, description="Default space quota for new users.")
    defaultgroupquota: PropertyValue = Field(default=NotRequired, description="Default space quota for new groups.")
    defaultprojectquota: PropertyValue = Field(default=NotRequired, description="Default space quota for new projects.")
    defaultuserobjquota: PropertyValue = Field(default=NotRequired, description="Default object quota for new users.")
    defaultgroupobjquota: PropertyValue = Field(default=NotRequired, description="Default object quota for new groups.")
    defaultprojectobjquota: PropertyValue = Field(
        default=NotRequired,
        description="Default object quota for new projects.",
    )
    # Volume snapshot specific properties
    volsize: PropertyValue = Field(default=NotRequired, description="Logical size of the volume.")


class ZFSResourceSnapshotEntry(BaseModel):
    createtxg: int = Field(description="The TXG in which the snapshot was created.")
    guid: int = Field(description="A GUID for the snapshot.")
    name: str = Field(description="The zfs resource for the given snapshot.")
    pool: str = Field(description="The zpool of the snapshot.")
    dataset: str = Field(description="The zfs resource for the given snapshot.")
    snapshot_name: str = Field(description="The name of the snapshot.")
    type: Literal["SNAPSHOT"] = Field(default="SNAPSHOT", description="The type of zfs resource.")
    holds: tuple | None = Field(description="A list of tags that hold the snapshot.")
    properties: ZFSResourceSnapshotPropertiesEntry | None = Field(description="Requested properties for the snapshot.")
    user_properties: dict[str, str] | None = Field(description="User-defined properties for snapshots.")


class ZFSResourceSnapshotQueryBase(BaseModel):
    paths: UniqueList[str] = Field(
        default=list(),
        description="Dataset paths to count snapshots for. If empty, counts all snapshots.",
    )
    recursive: bool = Field(default=False, description="Include snapshots from child datasets when counting.")


class ZFSResourceSnapshotQuery(ZFSResourceSnapshotQueryBase):
    properties: list[str] | None = Field(
        default=list(),
        description=(
            "List of ZFS properties to retrieve. Empty list returns default properties. None returns no properties."
        ),
    )
    get_user_properties: bool = Field(default=False, description="Retrieve user-defined properties for snapshots.")
    get_source: bool = Field(default=False, description="Include source information for each property value.")
    get_holds: bool = Field(default=False, description="Include holds information (if any) for the snapshot.")
    min_txg: int = Field(
        default=0,
        description="Minimum transaction group for filtering snapshots. 0 means no minimum.",
    )
    max_txg: int = Field(
        default=0,
        description="Maximum transaction group for filtering snapshots. 0 means no maximum.",
    )


class ZFSResourceSnapshotQueryArgs(BaseModel):
    data: ZFSResourceSnapshotQuery = Field(
        default=ZFSResourceSnapshotQuery(),
        description="Query parameters for retrieving ZFS snapshot information.",
    )


class ZFSResourceSnapshotQueryResult(BaseModel):
    result: list[ZFSResourceSnapshotEntry]


class ZFSResourceSnapshotCountQuery(ZFSResourceSnapshotQueryBase):
    pass


class ZFSResourceSnapshotCountArgs(BaseModel):
    data: ZFSResourceSnapshotCountQuery = Field(
        default=ZFSResourceSnapshotCountQuery(),
        description="Count parameters for counting ZFS snapshots.",
    )


class ZFSResourceSnapshotCountResult(BaseModel):
    result: dict[str, int] = Field(description="Mapping of dataset names to their snapshot counts.")


class ZFSResourceSnapshotDestroyQuery(BaseModel):
    path: NonEmptyString = Field(
        description=(
            "Path to destroy. Either a snapshot path (e.g., 'pool/dataset@snapshot') or a dataset path when "
            "all_snapshots=True (e.g., 'pool/dataset')."
        ),
    )
    recursive: bool = Field(default=False, description="Recursively destroy matching snapshots in child datasets.")
    all_snapshots: bool = Field(
        default=False,
        description="If True, path should be a dataset path and all its snapshots will be destroyed.",
    )
    defer: bool = Field(default=False, description="Defer destruction if snapshot is in use (e.g., has clones).")
    bypass: SkipJsonSchema[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent deleting zfs resources that are \"protected\"."
        ),
    )


class ZFSResourceSnapshotDestroyArgs(BaseModel):
    data: ZFSResourceSnapshotDestroyQuery = Field(description="Destroy parameters for removing ZFS snapshots.")


class ZFSResourceSnapshotDestroyResult(BaseModel):
    result: None


class ZFSResourceSnapshotRenameQuery(BaseModel):
    current_name: NonEmptyString = Field(description="Current snapshot path (e.g., 'pool/dataset@old_name').")
    new_name: NonEmptyString = Field(description="New snapshot path (e.g., 'pool/dataset@new_name').")
    recursive: bool = Field(default=False, description="Recursively rename matching snapshots in child datasets.")
    bypass: SkipJsonSchema[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent deleting zfs resources that are \"protected\"."
        ),
    )


class ZFSResourceSnapshotRenameArgs(BaseModel):
    data: ZFSResourceSnapshotRenameQuery = Field(description="Rename parameters for renaming ZFS snapshots.")


class ZFSResourceSnapshotRenameResult(BaseModel):
    result: None


class ZFSResourceSnapshotCloneQuery(BaseModel):
    snapshot: NonEmptyString = Field(description="Source snapshot path to clone (e.g., 'pool/dataset@snapshot').")
    dataset: NonEmptyString = Field(description="Destination dataset path for the clone (e.g., 'pool/clone').")
    properties: dict[str, str | int] = Field(default={}, description="ZFS properties to set on the cloned dataset.")
    bypass: SkipJsonSchema[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent deleting zfs resources that are \"protected\"."
        ),
    )


class ZFSResourceSnapshotCloneArgs(BaseModel):
    data: ZFSResourceSnapshotCloneQuery = Field(description="Clone parameters for cloning ZFS snapshots.")


class ZFSResourceSnapshotCloneResult(BaseModel):
    result: None


class ZFSResourceSnapshotCreateQuery(BaseModel):
    dataset: NonEmptyString = Field(description="Dataset path to snapshot (e.g., 'pool/dataset').")
    name: NonEmptyString = Field(description="Snapshot name (the part after @).")
    recursive: bool = Field(default=False, description="Create snapshots recursively for child datasets.")
    exclude: list[str] = Field(default=[], description="Datasets to exclude when creating recursive snapshots.")
    user_properties: dict[str, str] = Field(
        default={},
        description=(
            "User properties to set on the snapshot. Only user-defined properties are supported (e.g., "
            "'com.company:backup_type'). Regular ZFS properties cannot be set on snapshots at creation time."
        ),
    )
    bypass: SkipJsonSchema[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent deleting zfs resources that are \"protected\"."
        ),
    )


class ZFSResourceSnapshotCreateArgs(BaseModel):
    data: ZFSResourceSnapshotCreateQuery = Field(description="Create parameters for creating ZFS snapshots.")


class ZFSResourceSnapshotCreateResult(BaseModel):
    result: ZFSResourceSnapshotEntry


class ZFSResourceSnapshotHoldQuery(BaseModel):
    path: NonEmptyString = Field(description="Snapshot path to hold (e.g., 'pool/dataset@snapshot').")
    tag: str = Field(default="truenas", description="Hold tag name to apply.")
    recursive: bool = Field(
        default=False,
        description="Apply hold recursively to matching snapshots in child datasets.",
    )
    bypass: SkipJsonSchema[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent deleting zfs resources that are \"protected\"."
        ),
    )


class ZFSResourceSnapshotHoldArgs(BaseModel):
    data: ZFSResourceSnapshotHoldQuery = Field(description="Hold parameters for holding ZFS snapshots.")


class ZFSResourceSnapshotHoldResult(BaseModel):
    result: None


class ZFSResourceSnapshotHoldsQuery(BaseModel):
    path: NonEmptyString = Field(description="Snapshot path to query holds for (e.g., 'pool/dataset@snapshot').")


class ZFSResourceSnapshotHoldsArgs(BaseModel):
    data: ZFSResourceSnapshotHoldsQuery = Field(description="Query parameters for getting holds on a ZFS snapshot.")


class ZFSResourceSnapshotHoldsResult(BaseModel):
    result: list[str] = Field(description="List of hold tag names on the snapshot.")


class ZFSResourceSnapshotReleaseQuery(BaseModel):
    path: NonEmptyString = Field(description="Snapshot path to release holds from (e.g., 'pool/dataset@snapshot').")
    tag: str | None = Field(default=None, description="Specific tag to release. If None, releases all hold tags.")
    recursive: bool = Field(
        default=False,
        description="Release holds recursively from matching snapshots in child datasets.",
    )
    bypass: SkipJsonSchema[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent deleting zfs resources that are \"protected\"."
        ),
    )


class ZFSResourceSnapshotReleaseArgs(BaseModel):
    data: ZFSResourceSnapshotReleaseQuery = Field(
        description="Release parameters for releasing holds on ZFS snapshots.",
    )


class ZFSResourceSnapshotReleaseResult(BaseModel):
    result: None


class ZFSResourceSnapshotRollbackQuery(BaseModel):
    path: NonEmptyString = Field(description="Snapshot path to rollback to (e.g., 'pool/dataset@snapshot').")
    recursive: bool = Field(
        default=False,
        description="Destroy any snapshots and bookmarks more recent than the one specified.",
    )
    recursive_clones: bool = Field(default=False, description="Like recursive, but also destroy any clones.")
    force: bool = Field(default=False, description="Force unmount of any clones.")
    recursive_rollback: bool = Field(
        default=False,
        description="Do a complete recursive rollback of each child snapshot. Fails if any child lacks the snapshot.",
    )
    bypass: SkipJsonSchema[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent deleting zfs resources that are \"protected\"."
        ),
    )


class ZFSResourceSnapshotRollbackArgs(BaseModel):
    data: ZFSResourceSnapshotRollbackQuery = Field(description="Rollback parameters for rolling back to ZFS snapshots.")


class ZFSResourceSnapshotRollbackResult(BaseModel):
    result: None
