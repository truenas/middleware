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
    "ZFSResourceSnapshotReleaseArgs",
    "ZFSResourceSnapshotReleaseResult",
    "ZFSResourceSnapshotRollbackArgs",
    "ZFSResourceSnapshotRollbackResult",
)


class ZFSResourceSnapshotPropertiesEntry(BaseModel):
    # Common properties (both filesystem and volume snapshots)
    type: PropertyValue = NotRequired
    creation: PropertyValue = NotRequired
    used: PropertyValue = NotRequired
    referenced: PropertyValue = NotRequired
    compressratio: PropertyValue = NotRequired
    createtxg: PropertyValue = NotRequired
    guid: PropertyValue = NotRequired
    primarycache: PropertyValue = NotRequired
    secondarycache: PropertyValue = NotRequired
    objsetid: PropertyValue = NotRequired
    mlslabel: PropertyValue = NotRequired
    refcompressratio: PropertyValue = NotRequired
    written: PropertyValue = NotRequired
    logicalreferenced: PropertyValue = NotRequired
    context: PropertyValue = NotRequired
    fscontext: PropertyValue = NotRequired
    defcontext: PropertyValue = NotRequired
    rootcontext: PropertyValue = NotRequired
    encryption: PropertyValue = NotRequired
    encryptionroot: PropertyValue = NotRequired
    keystatus: PropertyValue = NotRequired
    redact_snaps: PropertyValue = NotRequired
    prefetch: PropertyValue = NotRequired
    # Filesystem snapshot specific properties
    devices: PropertyValue = NotRequired
    exec: PropertyValue = NotRequired
    setuid: PropertyValue = NotRequired
    xattr: PropertyValue = NotRequired
    version: PropertyValue = NotRequired
    utf8only: PropertyValue = NotRequired
    normalization: PropertyValue = NotRequired
    casesensitivity: PropertyValue = NotRequired
    nbmand: PropertyValue = NotRequired
    acltype: PropertyValue = NotRequired
    defaultuserquota: PropertyValue = NotRequired
    defaultgroupquota: PropertyValue = NotRequired
    defaultprojectquota: PropertyValue = NotRequired
    defaultuserobjquota: PropertyValue = NotRequired
    defaultgroupobjquota: PropertyValue = NotRequired
    defaultprojectobjquota: PropertyValue = NotRequired
    # Volume snapshot specific properties
    volsize: PropertyValue = NotRequired


class ZFSResourceSnapshotEntry(BaseModel):
    createtxg: int
    guid: int
    name: str
    pool: str
    dataset: str
    snapshot_name: str
    type: Literal["SNAPSHOT"] = "SNAPSHOT"
    properties: ZFSResourceSnapshotPropertiesEntry | None
    user_properties: dict[str, str] | None


class ZFSResourceSnapshotQuery(BaseModel):
    paths: UniqueList[str] = list()
    """Dataset paths or specific snapshot paths to query. If empty, queries all snapshots."""
    properties: list[str] | None = list()
    """List of ZFS properties to retrieve. Empty list returns default properties. None returns no properties."""
    get_user_properties: bool = False
    """Retrieve user-defined properties for snapshots."""
    get_source: bool = False
    """Include source information for each property value."""
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
    """Path to destroy. Either a snapshot path (e.g., 'pool/dataset@snapshot') or
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
