from typing import Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    NonEmptyString,
    NotRequired,
    Private,
    UniqueList,
    ZFSSpaceLimit,
    excluded_field,
)

from .zfs_resource_crud import PropertyValue, ZFSResourceSetProperties

__all__ = (
    "ZFSResourceSnapshotEntry",
    "ZFSResourceSnapshotPropertiesEntry",
    "ZFSResourceSnapshotQueryBase",
    "ZFSResourceSnapshotQuery",
    "ZFSResourceSnapshotListArgs",
    "ZFSResourceSnapshotListResult",
    "ZFSResourceSnapshotQueryArgs",
    "ZFSResourceSnapshotQueryResult",
    "ZFSResourceSnapshotCountQuery",
    "ZFSResourceSnapshotCountArgs",
    "ZFSResourceSnapshotCountResult",
    "ZFSResourceSnapshotDestroyArgsData",
    "ZFSResourceSnapshotDestroyArgs",
    "ZFSResourceSnapshotDestroyResult",
    "ZFSResourceSnapshotRenameArgsData",
    "ZFSResourceSnapshotRenameArgs",
    "ZFSResourceSnapshotRenameResult",
    "ZFSResourceSnapshotCloneProperties",
    "ZFSResourceSnapshotCloneArgsData",
    "ZFSResourceSnapshotCloneArgs",
    "ZFSResourceSnapshotCloneResult",
    "ZFSResourceSnapshotCreateArgsData",
    "ZFSResourceSnapshotCreateArgs",
    "ZFSResourceSnapshotCreateResult",
    "ZFSResourceSnapshotHoldArgsData",
    "ZFSResourceSnapshotHoldArgs",
    "ZFSResourceSnapshotHoldResult",
    "ZFSResourceSnapshotHoldsQuery",
    "ZFSResourceSnapshotHoldsArgs",
    "ZFSResourceSnapshotHoldsResult",
    "ZFSResourceSnapshotReleaseArgsData",
    "ZFSResourceSnapshotReleaseArgs",
    "ZFSResourceSnapshotReleaseResult",
    "ZFSResourceSnapshotRollbackArgsData",
    "ZFSResourceSnapshotRollbackArgs",
    "ZFSResourceSnapshotRollbackResult",
    "ZFSResourceSnapshotHoldsChange",
    "ZFSResourceSnapshotListAddedEvent",
    "ZFSResourceSnapshotListChangedEvent",
    "ZFSResourceSnapshotListRemovedEvent",
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
    name: str = Field(description="Full snapshot path (`dataset@snapshot`).")
    pool: str = Field(description="The zpool of the snapshot.")
    dataset: str = Field(description="Path of the filesystem or volume the snapshot was taken of.")
    snapshot_name: str = Field(description="The name of the snapshot.")
    type: Literal["SNAPSHOT"] = Field(default="SNAPSHOT", description="The type of zfs resource.")
    holds: tuple | None = Field(
        description=(
            "Hold tags on the snapshot when `get_holds` is set. Null when it is not set or the snapshot has no holds."
        ),
    )
    properties: ZFSResourceSnapshotPropertiesEntry | None = Field(
        description="The properties requested through `properties`.",
    )
    user_properties: dict[str, str] | None = Field(
        description="User properties of the snapshot when `get_user_properties` is set.",
    )


class ZFSResourceSnapshotQueryBase(BaseModel):
    paths: UniqueList[str] = Field(
        default=list(),
        description=(
            "Dataset paths, which select the snapshots of that dataset, and snapshot paths (`dataset@snapshot`), "
            "which select that one snapshot. A path that does not exist is skipped. When empty, the root "
            "filesystem of every imported pool is used."
        ),
    )
    recursive: bool = Field(
        default=False,
        description=(
            "Also include the snapshots of the descendants of each dataset path, or of every pool's root "
            "filesystem when `paths` is empty."
        ),
    )


class ZFSResourceSnapshotQuery(ZFSResourceSnapshotQueryBase):
    properties: list[str] | None = Field(
        default=list(),
        description=(
            "ZFS properties to retrieve for each snapshot. Snapshots have no default properties, so an empty list "
            "or null retrieves none."
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


class ZFSResourceSnapshotListArgs(BaseModel):
    data: ZFSResourceSnapshotQuery = Field(
        default_factory=ZFSResourceSnapshotQuery,
        description="Parameters selecting the snapshots to list and the information to retrieve.",
    )


class ZFSResourceSnapshotListResult(BaseModel):
    result: list[ZFSResourceSnapshotEntry]


class ZFSResourceSnapshotQueryArgs(ZFSResourceSnapshotListArgs):
    pass


class ZFSResourceSnapshotQueryResult(ZFSResourceSnapshotListResult):
    pass


class ZFSResourceSnapshotCountQuery(ZFSResourceSnapshotQueryBase):
    pass


class ZFSResourceSnapshotCountArgs(BaseModel):
    data: ZFSResourceSnapshotCountQuery = Field(
        default=ZFSResourceSnapshotCountQuery(),
        description="Count parameters for counting ZFS snapshots.",
    )


class ZFSResourceSnapshotCountResult(BaseModel):
    result: dict[str, int] = Field(description="Mapping of dataset names to their snapshot counts.")


class ZFSResourceSnapshotDestroyArgsData(BaseModel):
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
    bypass: Private[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent deleting zfs resources that are \"protected\"."
        ),
    )


class ZFSResourceSnapshotDestroyArgs(BaseModel):
    data: ZFSResourceSnapshotDestroyArgsData = Field(description="Destroy parameters for removing ZFS snapshots.")


class ZFSResourceSnapshotDestroyResult(BaseModel):
    result: None


class ZFSResourceSnapshotRenameArgsData(BaseModel):
    current_name: NonEmptyString = Field(description="Current snapshot path (e.g., 'pool/dataset@old_name').")
    new_name: NonEmptyString = Field(description="New snapshot path (e.g., 'pool/dataset@new_name').")
    recursive: bool = Field(default=False, description="Recursively rename matching snapshots in child datasets.")
    force: bool = Field(
        default=False,
        description=(
            "Acknowledge that no check is made whether the snapshot is in use. Replication, snapshot tasks and "
            "anything else that finds snapshots by name may break when one is renamed. The rename is refused "
            "unless this is set."
        ),
    )
    bypass: Private[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent renaming snapshots of \"protected\" zfs resources."
        ),
    )


class ZFSResourceSnapshotRenameArgs(BaseModel):
    data: ZFSResourceSnapshotRenameArgsData = Field(description="Rename parameters for renaming ZFS snapshots.")

    @classmethod
    def from_previous(cls, value):
        # Clients of the previous API had no `force` and were never refused.
        value["data"]["force"] = True
        return value


class ZFSResourceSnapshotRenameResult(BaseModel):
    result: None


class ZFSResourceSnapshotCloneProperties(ZFSResourceSetProperties):
    """ZFS properties that may be set when cloning a snapshot.

    Each field is the native ZFS property name and values are handed to ZFS verbatim.
    A field left as null is not sent to ZFS, so the clone inherits it as usual.
    Fields marked `Private` are settable by internal callers only.
    """

    volsize: Excluded = excluded_field()
    refreservation: ZFSSpaceLimit | Literal["auto"] | None = Field(
        default=None,
        description=(
            "Minimum space reserved for the clone itself, as a byte count or a size string such as '10G'. 'none' or "
            "0 reserves nothing. 'auto' reserves the space a volume's size requires and is accepted for volume "
            "clones only."
        ),
    )


class ZFSResourceSnapshotCloneArgsData(BaseModel):
    snapshot: NonEmptyString = Field(description="Source snapshot path to clone (e.g., 'pool/dataset@snapshot').")
    dataset: NonEmptyString = Field(description="Destination dataset path for the clone (e.g., 'pool/clone').")
    properties: ZFSResourceSnapshotCloneProperties = Field(
        default_factory=ZFSResourceSnapshotCloneProperties,
        description=(
            "ZFS properties to set on the clone. A property left as null is not sent to ZFS and inherits as usual. "
            "Any property not in this model may not be set on a clone, and a property that applies only to a "
            "filesystem or only to a volume is refused for the other type.\n"
            "\n"
            "On a filesystem clone an explicit 'acltype' also defaults the coupled acl properties. An nfsv4 acltype "
            "defaults 'aclinherit' to 'passthrough' while a posix or off acltype defaults both 'aclmode' and "
            "'aclinherit' to 'discard'."
        ),
    )
    user_properties: dict[str, str] = Field(
        default={},
        description=(
            "User properties to set on the clone, keyed by their full name (e.g. 'org.truenas:custom'). A name must "
            "contain a colon, may consist only of lowercase letters, digits and the characters ':', '.', '_' and "
            "'-', and must be shorter than 256 characters. A value must be shorter than 8192 bytes."
        ),
    )
    no_mount: bool = Field(
        default=False,
        description="Do not mount the clone after creating it. Volume clones are never mounted.",
    )
    bypass: Private[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent cloning from or into \"protected\" zfs resources. "
            "It also skips the `aclmode`/`aclinherit` defaults that follow an explicit `acltype`."
        ),
    )


class ZFSResourceSnapshotCloneArgs(BaseModel):
    data: ZFSResourceSnapshotCloneArgsData = Field(description="Clone parameters for cloning ZFS snapshots.")

    @classmethod
    def from_previous(cls, value):
        properties = value["data"].get("properties") or {}
        value["data"]["properties"] = {k: v for k, v in properties.items() if ":" not in k}
        value["data"]["user_properties"] = {k: str(v) for k, v in properties.items() if ":" in k}
        return value


class ZFSResourceSnapshotCloneResult(BaseModel):
    result: None


class ZFSResourceSnapshotCreateArgsData(BaseModel):
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
    bypass: Private[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent snapshotting \"protected\" zfs resources."
        ),
    )


class ZFSResourceSnapshotCreateArgs(BaseModel):
    data: ZFSResourceSnapshotCreateArgsData = Field(description="Create parameters for creating ZFS snapshots.")


class ZFSResourceSnapshotCreateResult(BaseModel):
    result: ZFSResourceSnapshotEntry


class ZFSResourceSnapshotHoldArgsData(BaseModel):
    path: NonEmptyString = Field(description="Snapshot path to hold (e.g., 'pool/dataset@snapshot').")
    tag: str = Field(default="truenas", description="Hold tag name to apply.")
    recursive: bool = Field(
        default=False,
        description="Apply hold recursively to matching snapshots in child datasets.",
    )
    bypass: Private[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent holding snapshots of \"protected\" zfs resources."
        ),
    )


class ZFSResourceSnapshotHoldArgs(BaseModel):
    data: ZFSResourceSnapshotHoldArgsData = Field(description="Hold parameters for holding ZFS snapshots.")


class ZFSResourceSnapshotHoldResult(BaseModel):
    result: None


class ZFSResourceSnapshotHoldsQuery(BaseModel):
    path: NonEmptyString = Field(description="Snapshot path to query holds for (e.g., 'pool/dataset@snapshot').")


class ZFSResourceSnapshotHoldsArgs(BaseModel):
    data: ZFSResourceSnapshotHoldsQuery = Field(description="Query parameters for getting holds on a ZFS snapshot.")


class ZFSResourceSnapshotHoldsResult(BaseModel):
    result: list[str] = Field(description="List of hold tag names on the snapshot.")


class ZFSResourceSnapshotReleaseArgsData(BaseModel):
    path: NonEmptyString = Field(description="Snapshot path to release holds from (e.g., 'pool/dataset@snapshot').")
    tag: str | None = Field(default=None, description="Specific tag to release. If None, releases all hold tags.")
    recursive: bool = Field(
        default=False,
        description="Release holds recursively from matching snapshots in child datasets.",
    )
    bypass: Private[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent releasing holds on snapshots of \"protected\" zfs "
            "resources."
        ),
    )


class ZFSResourceSnapshotReleaseArgs(BaseModel):
    data: ZFSResourceSnapshotReleaseArgsData = Field(
        description="Release parameters for releasing holds on ZFS snapshots.",
    )


class ZFSResourceSnapshotReleaseResult(BaseModel):
    result: None


class ZFSResourceSnapshotRollbackArgsData(BaseModel):
    path: NonEmptyString = Field(description="Snapshot path to rollback to (e.g., 'pool/dataset@snapshot').")
    recursive: bool = Field(
        default=False,
        description="Destroy any snapshots more recent than the one specified.",
    )
    recursive_clones: bool = Field(default=False, description="Like recursive, but also destroy any clones.")
    force: bool = Field(default=False, description="Force unmount of any clones.")
    recursive_rollback: bool = Field(
        default=False,
        description="Do a complete recursive rollback of each child snapshot. Fails if any child lacks the snapshot.",
    )
    bypass: Private[bool] = Field(
        default=False,
        description=(
            "If true, will bypass the safety checks that prevent rolling back \"protected\" zfs resources."
        ),
    )


class ZFSResourceSnapshotRollbackArgs(BaseModel):
    data: ZFSResourceSnapshotRollbackArgsData = Field(
        description="Rollback parameters for rolling back to ZFS snapshots.",
    )


class ZFSResourceSnapshotRollbackResult(BaseModel):
    result: None


class ZFSResourceSnapshotHoldsChange(BaseModel):
    holds: list[str] = Field(description="Hold tags on the snapshot after the operation.")


class ZFSResourceSnapshotListAddedEvent(BaseModel):
    id: str = Field(description="Path of the snapshot that was created or renamed into place.")
    fields: ZFSResourceSnapshotEntry = Field(description="The snapshot as read back after the operation.")


class ZFSResourceSnapshotListChangedEvent(BaseModel):
    id: str = Field(description="Path of the snapshot whose holds changed.")
    fields: ZFSResourceSnapshotHoldsChange = Field(description="The holds of the snapshot after a hold or release.")


class ZFSResourceSnapshotListRemovedEvent(BaseModel):
    id: str = Field(description="Path of the snapshot that was destroyed or renamed away.")
