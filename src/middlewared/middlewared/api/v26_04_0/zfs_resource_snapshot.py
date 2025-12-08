from typing import Literal

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
    "ZFSResourceSnapshotQueryArgs",
    "ZFSResourceSnapshotQueryResult",
    "ZFSResourceSnapshotCountArgs",
    "ZFSResourceSnapshotCountResult",
    "ZFSResourceSnapshotDestroyArgs",
    "ZFSResourceSnapshotDestroyResult",
    "ZFSResourceSnapshotRenameArgs",
    "ZFSResourceSnapshotRenameResult",
    "ZFSResourceSnapshotCloneArgs",
    "ZFSResourceSnapshotCloneResult",
    "ZFSResourceSnapshotCreateArgs",
    "ZFSResourceSnapshotCreateResult",
    "ZFSResourceSnapshotHoldArgs",
    "ZFSResourceSnapshotHoldResult",
    "ZFSResourceSnapshotHoldsArgs",
    "ZFSResourceSnapshotHoldsResult",
    "ZFSResourceSnapshotReleaseArgs",
    "ZFSResourceSnapshotReleaseResult",
    "ZFSResourceSnapshotRollbackArgs",
    "ZFSResourceSnapshotRollbackResult",
)


class ZFSResourceSnapshotPropertiesEntry(BaseModel):
    # Common properties (both filesystem and volume snapshots)
    type: PropertyValue = NotRequired
    """(READ-ONLY): Type of ZFS dataset (filesystem, volume, etc)."""
    creation: PropertyValue = NotRequired
    """(READ-ONLY): Timestamp when dataset was created."""
    used: PropertyValue = NotRequired
    """(READ-ONLY): Space used by dataset and descendants."""
    referenced: PropertyValue = NotRequired
    """(READ-ONLY): Space referenced by this dataset."""
    compressratio: PropertyValue = NotRequired
    """(READ-ONLY): Property showing achieved compression ratio."""
    createtxg: PropertyValue = NotRequired
    """(READ-ONLY): Transaction group when dataset was created."""
    guid: PropertyValue = NotRequired
    """(READ-ONLY): Globally unique identifier for the dataset."""
    primarycache: PropertyValue = NotRequired
    """Controls primary cache usage (all, metadata, or none)."""
    secondarycache: PropertyValue = NotRequired
    """Controls secondary cache usage (all, metadata, or none)."""
    objsetid: PropertyValue = NotRequired
    """(READ-ONLY): Object set identifier for the dataset."""
    mlslabel: PropertyValue = NotRequired
    """Multi-level security label for the dataset."""
    refcompressratio: PropertyValue = NotRequired
    """(READ-ONLY): Compression ratio for referenced data."""
    written: PropertyValue = NotRequired
    """(READ-ONLY): Space referenced since previous snapshot."""
    logicalreferenced: PropertyValue = NotRequired
    """(READ-ONLY): Logical space referenced by dataset."""
    context: PropertyValue = NotRequired
    """SELinux security context for the dataset."""
    fscontext: PropertyValue = NotRequired
    """SELinux filesystem security context."""
    defcontext: PropertyValue = NotRequired
    """SELinux default security context for new files."""
    rootcontext: PropertyValue = NotRequired
    """SELinux root directory security context."""
    encryption: PropertyValue = NotRequired
    """Controls encryption cipher suite for the dataset."""
    encryptionroot: PropertyValue = NotRequired
    """(READ-ONLY): Property showing encryption root dataset."""
    keystatus: PropertyValue = NotRequired
    """(READ-ONLY): Encryption key status (available/unavailable)."""
    redact_snaps: PropertyValue = NotRequired
    """(READ-ONLY): List of redaction snapshots."""
    prefetch: PropertyValue = NotRequired
    """Controls prefetch behavior (all, metadata, or none)."""
    # Filesystem snapshot specific properties
    devices: PropertyValue = NotRequired
    """Controls whether device files can be opened."""
    exec: PropertyValue = NotRequired
    """Controls whether programs can be executed from filesystem."""
    setuid: PropertyValue = NotRequired
    """Controls setuid/setgid bit respect on executable files."""
    xattr: PropertyValue = NotRequired
    """Controls extended attribute behavior (on, off, sa, dir)."""
    version: PropertyValue = NotRequired
    """(READ-ONLY): Filesystem version number."""
    utf8only: PropertyValue = NotRequired
    """Controls whether only UTF-8 filenames are allowed."""
    normalization: PropertyValue = NotRequired
    """Unicode normalization property for filenames."""
    casesensitivity: PropertyValue = NotRequired
    """Determines filename matching algorithm sensitivity."""
    nbmand: PropertyValue = NotRequired
    """Controls non-blocking mandatory locking behavior."""
    acltype: PropertyValue = NotRequired
    """Specifies type of ACL to use (off, nfsv4, posix)."""
    defaultuserquota: PropertyValue = NotRequired
    """Default space quota for new users."""
    defaultgroupquota: PropertyValue = NotRequired
    """Default space quota for new groups."""
    defaultprojectquota: PropertyValue = NotRequired
    """Default space quota for new projects."""
    defaultuserobjquota: PropertyValue = NotRequired
    """Default object quota for new users."""
    defaultgroupobjquota: PropertyValue = NotRequired
    """Default object quota for new groups."""
    defaultprojectobjquota: PropertyValue = NotRequired
    """Default object quota for new projects."""
    # Volume snapshot specific properties
    volsize: PropertyValue = NotRequired
    """Logical size of the volume."""


class ZFSResourceSnapshotEntry(BaseModel):
    createtxg: int
    """The TXG in which the snapshot was created."""
    guid: int
    """A GUID for the snapshot."""
    name: str
    """The zfs resource for the given snapshot."""
    pool: str
    """The zpool of the snapshot."""
    dataset: str
    """The zfs resource for the given snapshot."""
    snapshot_name: str
    """The name of the snapshot."""
    type: Literal["SNAPSHOT"] = "SNAPSHOT"
    """The type of zfs resource."""
    holds: tuple[str] | None
    """A list of tags that hold the snapshot."""
    properties: ZFSResourceSnapshotPropertiesEntry | None
    """Requested properties for the snapshot."""
    user_properties: dict[str, str] | None
    """User-defined properties for snapshots."""


class ZFSResourceSnapshotQuery(BaseModel):
    paths: UniqueList[str] = list()
    """Dataset paths or specific snapshot paths to query. If empty, queries all snapshots."""
    properties: list[str] | None = list()
    """List of ZFS properties to retrieve. Empty list returns default properties. None returns no properties."""
    get_user_properties: bool = False
    """Retrieve user-defined properties for snapshots."""
    get_source: bool = False
    """Include source information for each property value."""
    get_holds: bool = False
    """Include holds information (if any) for the snapshot."""
    recursive: bool = False
    """Include snapshots from child datasets when querying dataset paths."""
    min_txg: int = 0
    """Minimum transaction group for filtering snapshots. 0 means no minimum."""
    max_txg: int = 0
    """Maximum transaction group for filtering snapshots. 0 means no maximum."""


class ZFSResourceSnapshotQueryArgs(BaseModel):
    data: ZFSResourceSnapshotQuery = ZFSResourceSnapshotQuery()
    """Query parameters for retrieving ZFS snapshot information."""


class ZFSResourceSnapshotQueryResult(BaseModel):
    result: list[ZFSResourceSnapshotEntry]


class ZFSResourceSnapshotCountQuery(BaseModel):
    paths: UniqueList[str] = list()
    """Dataset paths to count snapshots for. If empty, counts all snapshots."""
    recursive: bool = False
    """Include snapshots from child datasets when counting."""


class ZFSResourceSnapshotCountArgs(BaseModel):
    data: ZFSResourceSnapshotCountQuery = ZFSResourceSnapshotCountQuery()
    """Count parameters for counting ZFS snapshots."""


class ZFSResourceSnapshotCountResult(BaseModel):
    result: dict[str, int]
    """Mapping of dataset names to their snapshot counts."""


class ZFSResourceSnapshotDestroyQuery(BaseModel):
    path: NonEmptyString
    """Path to destroy. Either a snapshot path (e.g., 'pool/dataset@snapshot') or \
    a dataset path when all_snapshots=True (e.g., 'pool/dataset')."""
    recursive: bool = False
    """Recursively destroy matching snapshots in child datasets."""
    all_snapshots: bool = False
    """If True, path should be a dataset path and all its snapshots will be destroyed."""
    defer: bool = False
    """Defer destruction if snapshot is in use (e.g., has clones)."""


class ZFSResourceSnapshotDestroyArgs(BaseModel):
    data: ZFSResourceSnapshotDestroyQuery
    """Destroy parameters for removing ZFS snapshots."""


class ZFSResourceSnapshotDestroyResult(BaseModel):
    result: None


class ZFSResourceSnapshotRenameQuery(BaseModel):
    current_name: NonEmptyString
    """Current snapshot path (e.g., 'pool/dataset@old_name')."""
    new_name: NonEmptyString
    """New snapshot path (e.g., 'pool/dataset@new_name')."""
    recursive: bool = False
    """Recursively rename matching snapshots in child datasets."""


class ZFSResourceSnapshotRenameArgs(BaseModel):
    data: ZFSResourceSnapshotRenameQuery
    """Rename parameters for renaming ZFS snapshots."""


class ZFSResourceSnapshotRenameResult(BaseModel):
    result: None


class ZFSResourceSnapshotCloneQuery(BaseModel):
    snapshot: NonEmptyString
    """Source snapshot path to clone (e.g., 'pool/dataset@snapshot')."""
    dataset: NonEmptyString
    """Destination dataset path for the clone (e.g., 'pool/clone')."""
    properties: dict[str, str | int] = {}
    """ZFS properties to set on the cloned dataset."""


class ZFSResourceSnapshotCloneArgs(BaseModel):
    data: ZFSResourceSnapshotCloneQuery
    """Clone parameters for cloning ZFS snapshots."""


class ZFSResourceSnapshotCloneResult(BaseModel):
    result: None


class ZFSResourceSnapshotCreateQuery(BaseModel):
    dataset: NonEmptyString
    """Dataset path to snapshot (e.g., 'pool/dataset')."""
    name: NonEmptyString
    """Snapshot name (the part after @)."""
    recursive: bool = False
    """Create snapshots recursively for child datasets."""
    exclude: list[str] = []
    """Datasets to exclude when creating recursive snapshots."""
    user_properties: dict[str, str] = {}
    """User properties to set on the snapshot. Only user-defined properties are
    supported (e.g., 'com.company:backup_type'). Regular ZFS properties cannot
    be set on snapshots at creation time."""


class ZFSResourceSnapshotCreateArgs(BaseModel):
    data: ZFSResourceSnapshotCreateQuery
    """Create parameters for creating ZFS snapshots."""


class ZFSResourceSnapshotCreateResult(BaseModel):
    result: ZFSResourceSnapshotEntry


class ZFSResourceSnapshotHoldQuery(BaseModel):
    path: NonEmptyString
    """Snapshot path to hold (e.g., 'pool/dataset@snapshot')."""
    tag: str = "truenas"
    """Hold tag name to apply."""
    recursive: bool = False
    """Apply hold recursively to matching snapshots in child datasets."""


class ZFSResourceSnapshotHoldArgs(BaseModel):
    data: ZFSResourceSnapshotHoldQuery
    """Hold parameters for holding ZFS snapshots."""


class ZFSResourceSnapshotHoldResult(BaseModel):
    result: None


class ZFSResourceSnapshotHoldsQuery(BaseModel):
    path: NonEmptyString
    """Snapshot path to query holds for (e.g., 'pool/dataset@snapshot')."""


class ZFSResourceSnapshotHoldsArgs(BaseModel):
    data: ZFSResourceSnapshotHoldsQuery
    """Query parameters for getting holds on a ZFS snapshot."""


class ZFSResourceSnapshotHoldsResult(BaseModel):
    result: list[str]
    """List of hold tag names on the snapshot."""


class ZFSResourceSnapshotReleaseQuery(BaseModel):
    path: NonEmptyString
    """Snapshot path to release holds from (e.g., 'pool/dataset@snapshot')."""
    tag: str | None = None
    """Specific tag to release. If None, releases all hold tags."""
    recursive: bool = False
    """Release holds recursively from matching snapshots in child datasets."""


class ZFSResourceSnapshotReleaseArgs(BaseModel):
    data: ZFSResourceSnapshotReleaseQuery
    """Release parameters for releasing holds on ZFS snapshots."""


class ZFSResourceSnapshotReleaseResult(BaseModel):
    result: None


class ZFSResourceSnapshotRollbackQuery(BaseModel):
    path: NonEmptyString
    """Snapshot path to rollback to (e.g., 'pool/dataset@snapshot')."""
    recursive: bool = False
    """Destroy any snapshots and bookmarks more recent than the one specified."""
    recursive_clones: bool = False
    """Like recursive, but also destroy any clones."""
    force: bool = False
    """Force unmount of any clones."""
    recursive_rollback: bool = False
    """Do a complete recursive rollback of each child snapshot. Fails if any child lacks the snapshot."""


class ZFSResourceSnapshotRollbackArgs(BaseModel):
    data: ZFSResourceSnapshotRollbackQuery
    """Rollback parameters for rolling back to ZFS snapshots."""


class ZFSResourceSnapshotRollbackResult(BaseModel):
    result: None
