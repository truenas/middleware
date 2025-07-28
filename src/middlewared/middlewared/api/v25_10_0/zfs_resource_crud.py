from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, NotRequired, UniqueList

__all__ = ("ZFSResourceEntry", "ZFSResourceQueryArgs", "ZFSResourceQueryResult")
READ_ONLY = "(READ-ONLY):"
PROP_SRC = Literal["NONE", "DEFAULT", "TEMPORARY", "LOCAL", "INHERITED", "RECEIVED"]


class SourceValue(BaseModel):
    type: PROP_SRC
    """The source type."""
    value: str | None
    """The source value."""


class PropertyValue(BaseModel):
    raw: str
    """The raw value of the property."""
    source: SourceValue | None
    """The source from where this property received its value."""
    value: int | float | str | bool | None
    """The parsed raw value of the property."""


class ZFSPropertiesEntry(BaseModel):
    aclinherit: PropertyValue = NotRequired
    """Controls how ACEs are inherited for new files/directories."""
    aclmode: PropertyValue = NotRequired
    """Determines how ACLs are modified during chmod operations."""
    acltype: PropertyValue = NotRequired
    """Specifies type of ACL to use (off, nfsv4, posix)."""
    atime: PropertyValue = NotRequired
    """Controls whether access time is updated on file reads."""
    canmount: PropertyValue = NotRequired
    """Controls whether filesystem can be mounted."""
    casesensitivity: PropertyValue = NotRequired
    """Determines filename matching algorithm sensitivity."""
    defaultgroupobjquota: PropertyValue = NotRequired
    """Default object quota for new groups."""
    defaultgroupquota: PropertyValue = NotRequired
    """Default space quota for new groups."""
    defaultprojectobjquota: PropertyValue = NotRequired
    """Default object quota for new projects."""
    defaultprojectquota: PropertyValue = NotRequired
    """Default space quota for new projects."""
    defaultuserobjquota: PropertyValue = NotRequired
    """Default object quota for new users."""
    defaultuserquota: PropertyValue = NotRequired
    """Default space quota for new users."""
    devices: PropertyValue = NotRequired
    """Controls whether device files can be opened."""
    direct: PropertyValue = NotRequired
    """Controls direct I/O behavior (standard or always)."""
    dnodesize: PropertyValue = NotRequired
    """Controls dnode size for new objects."""
    exec: PropertyValue = NotRequired
    """Controls whether programs can be executed from filesystem."""
    filesystem_count: PropertyValue = NotRequired
    f"""{READ_ONLY} count of child filesystems."""
    filesystem_limit: PropertyValue = NotRequired
    """Maximum number of child filesystems allowed."""
    longname: PropertyValue = NotRequired
    """Controls support for long filenames."""
    mounted: PropertyValue = NotRequired
    f"""{READ_ONLY} property indicating if filesystem is mounted."""
    mountpoint: PropertyValue = NotRequired
    """Controls mount point used for this filesystem."""
    nbmand: PropertyValue = NotRequired
    """Controls non-blocking mandatory locking behavior."""
    normalization: PropertyValue = NotRequired
    """Unicode normalization property for filenames."""
    overlay: PropertyValue = NotRequired
    """Controls overlay mount behavior."""
    quota: PropertyValue = NotRequired
    """Limits space consumed by dataset and descendants."""
    recordsize: PropertyValue = NotRequired
    """Maximum block size for files in this filesystem."""
    refquota: PropertyValue = NotRequired
    """Limits space consumed by dataset itself (no descendants)."""
    refreservation: PropertyValue = NotRequired
    """Minimum space reserved for dataset itself (no descendants)."""
    relatime: PropertyValue = NotRequired
    """Controls relative access time updates."""
    setuid: PropertyValue = NotRequired
    """Controls setuid/setgid bit respect on executable files."""
    sharenfs: PropertyValue = NotRequired
    """Controls NFS sharing options for the filesystem."""
    sharesmb: PropertyValue = NotRequired
    """Controls SMB/CIFS sharing options for the filesystem."""
    snapdir: PropertyValue = NotRequired
    """Controls snapshot directory visibility (hidden or visible)."""
    special_small_blocks: PropertyValue = NotRequired
    """Size threshold for storing blocks on special vdevs."""
    utf8only: PropertyValue = NotRequired
    """Controls whether only UTF-8 filenames are allowed."""
    version: PropertyValue = NotRequired
    f"""{READ_ONLY} filesystem version number."""
    volmode: PropertyValue = NotRequired
    """Controls volume mode (default, geom, dev, none)."""
    vscan: PropertyValue = NotRequired
    """Controls virus scanning behavior."""
    xattr: PropertyValue = NotRequired
    """Controls extended attribute behavior (on, off, sa, dir)."""
    zoned: PropertyValue = NotRequired
    """Controls whether filesystem is managed from a zone."""
    available: PropertyValue = NotRequired
    """Amount of space available to dataset and its children."""
    checksum: PropertyValue = NotRequired
    """Controls checksum algorithm used to verify data integrity."""
    compression: PropertyValue = NotRequired
    """Controls compression algorithm used for this dataset."""
    compressratio: PropertyValue = NotRequired
    f"""{READ_ONLY} property showing achieved compression ratio."""
    context: PropertyValue = NotRequired
    """SELinux security context for the dataset."""
    copies: PropertyValue = NotRequired
    """Controls number of copies of data stored (1, 2, or 3)."""
    createtxg: PropertyValue = NotRequired
    f"""{READ_ONLY} transaction group when dataset was created."""
    creation: PropertyValue = NotRequired
    f"""{READ_ONLY} timestamp when dataset was created."""
    dedup: PropertyValue = NotRequired
    """Controls data deduplication for the dataset."""
    defcontext: PropertyValue = NotRequired
    """SELinux default security context for new files."""
    encryption: PropertyValue = NotRequired
    """Controls encryption cipher suite for the dataset."""
    encryptionroot: PropertyValue = NotRequired
    f"""{READ_ONLY} property showing encryption root dataset."""
    fscontext: PropertyValue = NotRequired
    """SELinux filesystem security context."""
    guid: PropertyValue = NotRequired
    f"""{READ_ONLY} globally unique identifier for the dataset."""
    keyformat: PropertyValue = NotRequired
    """Encryption key format (raw, hex, or passphrase)."""
    keylocation: PropertyValue = NotRequired
    """Location where encryption key is stored."""
    keystatus: PropertyValue = NotRequired
    f"""{READ_ONLY} encryption key status (available/unavailable)."""
    logbias: PropertyValue = NotRequired
    """Controls ZIL write behavior (latency or throughput)."""
    logicalreferenced: PropertyValue = NotRequired
    f"""{READ_ONLY} logical space referenced by dataset."""
    logicalused: PropertyValue = NotRequired
    f"""{READ_ONLY} logical space used by dataset and descendants."""
    mlslabel: PropertyValue = NotRequired
    """Multi-level security label for the dataset."""
    objsetid: PropertyValue = NotRequired
    f"""{READ_ONLY} object set identifier for the dataset."""
    origin: PropertyValue = NotRequired
    f"""{READ_ONLY} snapshot this dataset was cloned from."""
    pbkdf2iters: PropertyValue = NotRequired
    """Number of PBKDF2 iterations for key derivation."""
    prefetch: PropertyValue = NotRequired
    """Controls prefetch behavior (all, metadata, or none)."""
    primarycache: PropertyValue = NotRequired
    """Controls primary cache usage (all, metadata, or none)."""
    readonly: PropertyValue = NotRequired
    """Controls whether dataset can be modified."""
    receive_resume_token: PropertyValue = NotRequired
    f"""{READ_ONLY} token for resuming interrupted zfs receive."""
    redact_snaps: PropertyValue = NotRequired
    f"""{READ_ONLY} list of redaction snapshots."""
    redundant_metadata: PropertyValue = NotRequired
    """Controls redundant metadata storage (all or most)."""
    refcompressratio: PropertyValue = NotRequired
    f"""{READ_ONLY} compression ratio for referenced data."""
    referenced: PropertyValue = NotRequired
    f"""{READ_ONLY} space referenced by this dataset."""
    reservation: PropertyValue = NotRequired
    """Minimum space reserved for dataset and descendants."""
    rootcontext: PropertyValue = NotRequired
    """SELinux root directory security context."""
    secondarycache: PropertyValue = NotRequired
    """Controls secondary cache usage (all, metadata, or none)."""
    snapdev: PropertyValue = NotRequired
    """Controls snapshot device visibility (hidden or visible)."""
    snapshot_count: PropertyValue = NotRequired
    f"""{READ_ONLY} count of snapshots in this dataset."""
    snapshot_limit: PropertyValue = NotRequired
    """Maximum number of snapshots allowed."""
    snapshots_changed: PropertyValue = NotRequired
    f"""{READ_ONLY} property indicating snapshot changes."""
    sync: PropertyValue = NotRequired
    """Controls synchronous write behavior (standard, always, disabled)."""
    type: PropertyValue | None = NotRequired
    f"""{READ_ONLY} type of ZFS dataset (filesystem, volume, etc)."""
    used: PropertyValue = NotRequired
    f"""{READ_ONLY} space used by dataset and descendants."""
    usedbychildren: PropertyValue = NotRequired
    f"""{READ_ONLY} space used by child datasets."""
    usedbydataset: PropertyValue = NotRequired
    f"""{READ_ONLY} space used by this dataset itself."""
    usedbyrefreservation: PropertyValue = NotRequired
    f"""{READ_ONLY} space used by refreservation."""
    usedbysnapshots: PropertyValue = NotRequired
    f"""{READ_ONLY} space used by snapshots."""
    written: PropertyValue = NotRequired
    f"""{READ_ONLY} space referenced since previous snapshot."""
    refreservation: PropertyValue = NotRequired
    """Minimum space reserved for volume itself."""
    volblocksize: PropertyValue = NotRequired
    """Block size for volume (typically 8K or 16K)."""
    volmode: PropertyValue = NotRequired
    """Controls volume mode (default, geom, dev, none)."""
    volsize: PropertyValue = NotRequired
    """Logical size of the volume."""
    volthreading: PropertyValue = NotRequired
    """Controls volume threading behavior."""


class ZFSResourceEntry(BaseModel):
    createtxg: int
    """Transaction group when resource was created."""
    guid: int
    """Globally unique identifier for the resource."""
    name: str
    """The name of the zfs resource."""
    pool: str
    """The name of the zpool that the zfs resouce is associated to."""
    properties: ZFSPropertiesEntry
    """The zfs properties for the resource."""
    type: Literal["FILESYSTEM", "VOLUME"]
    """The type of ZFS resource."""
    user_properties: dict[str, str] | None
    """Custom metadata properties with colon-separated names (max 256 chars)."""
    children: list
    """The children of this zfs resource."""


class ZFSResourceQuery(BaseModel):
    paths: UniqueList[str] = list()
    """A list of zfs filesystem or volume paths to be queried. \
    In almost all scenarios, you should provide a path of what you \
    want to query. By providing path(s) here, it allows the API to \
    apply optimizations so that the requested information is retrieved \
    as efficiently and quickly as possible.

    Example 1:
        {"paths": ["tank/foo"]} will query the relevant information for \
            this resource only.
    Example 2:
        {"paths": ["tank/foo", "dozer/test"]} will query the relevant \
            information for these resources only.

    NOTE:
        paths must be non-overlapping if `get_children` is True.
        (i.e. this won't work and will raise a validation error)
            {
                "paths": ["tank/foo1", "tank/foo1/foo2"],
                "get_children": True
            }
    """
    properties: list[str] | None = list()
    """A list of zfs properties to be retrieved. Defaults to an \
    empty list which will return a default set of zfs properties.
    Setting this to None will retrieve no zfs properties."""
    get_user_properties: bool = False
    """Retrieve user properties for zfs resource(s)."""
    get_source: bool = Field(default=True, exclude_json_schema=True)
    """Hidden field to retrieve source information for a zfs property.

    NOTE: This should only ever be toggled by internal consumers and \
    you should know what you're doing by toggling this to False."""
    nest_results: bool = False
    """Return a nested object that associates all children to their \
    respective parents in the filesystem. By default, each zfs resource \
    is returned as a separate item in the array and is not associated \
    to its parent."""
    get_children: bool = False
    """Retrieve children information for the zfs resource."""


class ZFSResourceQueryArgs(BaseModel):
    data: ZFSResourceQuery = ZFSResourceQuery()


class ZFSResourceQueryResult(BaseModel):
    result: list[ZFSResourceEntry]
