from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, NotRequired, UniqueList

__all__ = ("ZFSResourceEntry", "ZFSResourceQueryArgs", "ZFSResourceQueryResult")

PROP_SRC = Literal["NONE", "DEFAULT", "TEMPORARY", "LOCAL", "INHERITED", "RECEIVED"]


class SourceValue(BaseModel):
    type: PROP_SRC = Field(description="The source type.")
    value: str | None = Field(description="The source value.")


class PropertyValue(BaseModel):
    raw: str = Field(description="The raw value of the property.")
    source: SourceValue | None = Field(description="The source from where this property received its value.")
    value: int | float | str | bool | None = Field(description="The parsed raw value of the property.")


class ZFSPropertiesEntry(BaseModel):
    aclinherit: PropertyValue = Field(
        default=NotRequired,
        description="Controls how ACEs are inherited for new files/directories.",
    )
    aclmode: PropertyValue = Field(
        default=NotRequired,
        description="Determines how ACLs are modified during chmod operations.",
    )
    acltype: PropertyValue = Field(default=NotRequired, description="Specifies type of ACL to use (off, nfsv4, posix).")
    atime: PropertyValue = Field(
        default=NotRequired,
        description="Controls whether access time is updated on file reads.",
    )
    canmount: PropertyValue = Field(default=NotRequired, description="Controls whether filesystem can be mounted.")
    casesensitivity: PropertyValue = Field(
        default=NotRequired,
        description="Determines filename matching algorithm sensitivity.",
    )
    defaultgroupobjquota: PropertyValue = Field(default=NotRequired, description="Default object quota for new groups.")
    defaultgroupquota: PropertyValue = Field(default=NotRequired, description="Default space quota for new groups.")
    defaultprojectobjquota: PropertyValue = Field(
        default=NotRequired,
        description="Default object quota for new projects.",
    )
    defaultprojectquota: PropertyValue = Field(default=NotRequired, description="Default space quota for new projects.")
    defaultuserobjquota: PropertyValue = Field(default=NotRequired, description="Default object quota for new users.")
    defaultuserquota: PropertyValue = Field(default=NotRequired, description="Default space quota for new users.")
    devices: PropertyValue = Field(default=NotRequired, description="Controls whether device files can be opened.")
    direct: PropertyValue = Field(default=NotRequired, description="Controls direct I/O behavior (standard or always).")
    dnodesize: PropertyValue = Field(default=NotRequired, description="Controls dnode size for new objects.")
    exec: PropertyValue = Field(
        default=NotRequired,
        description="Controls whether programs can be executed from filesystem.",
    )
    filesystem_count: PropertyValue = Field(default=NotRequired, description="(READ-ONLY): Count of child filesystems.")
    filesystem_limit: PropertyValue = Field(
        default=NotRequired,
        description="Maximum number of child filesystems allowed.",
    )
    longname: PropertyValue = Field(default=NotRequired, description="Controls support for long filenames.")
    mounted: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Property indicating if filesystem is mounted.",
    )
    mountpoint: PropertyValue = Field(default=NotRequired, description="Controls mount point used for this filesystem.")
    nbmand: PropertyValue = Field(default=NotRequired, description="Controls non-blocking mandatory locking behavior.")
    normalization: PropertyValue = Field(
        default=NotRequired,
        description="Unicode normalization property for filenames.",
    )
    overlay: PropertyValue = Field(default=NotRequired, description="Controls overlay mount behavior.")
    quota: PropertyValue = Field(default=NotRequired, description="Limits space consumed by dataset and descendants.")
    recordsize: PropertyValue = Field(
        default=NotRequired,
        description="Maximum block size for files in this filesystem.",
    )
    refquota: PropertyValue = Field(
        default=NotRequired,
        description="Limits space consumed by dataset itself (no descendants).",
    )
    refreservation: PropertyValue = Field(
        default=NotRequired,
        description="Minimum space reserved for dataset itself (no descendants).",
    )
    relatime: PropertyValue = Field(default=NotRequired, description="Controls relative access time updates.")
    setuid: PropertyValue = Field(
        default=NotRequired,
        description="Controls setuid/setgid bit respect on executable files.",
    )
    sharenfs: PropertyValue = Field(default=NotRequired, description="Controls NFS sharing options for the filesystem.")
    sharesmb: PropertyValue = Field(
        default=NotRequired,
        description="Controls SMB/CIFS sharing options for the filesystem.",
    )
    snapdir: PropertyValue = Field(
        default=NotRequired,
        description="Controls snapshot directory visibility (hidden or visible).",
    )
    special_small_blocks: PropertyValue = Field(
        default=NotRequired,
        description="Size threshold for storing blocks on special vdevs.",
    )
    utf8only: PropertyValue = Field(
        default=NotRequired,
        description="Controls whether only UTF-8 filenames are allowed.",
    )
    version: PropertyValue = Field(default=NotRequired, description="(READ-ONLY): Filesystem version number.")
    volmode: PropertyValue = Field(default=NotRequired, description="Controls volume mode (default, geom, dev, none).")
    vscan: PropertyValue = Field(default=NotRequired, description="Controls virus scanning behavior.")
    xattr: PropertyValue = Field(
        default=NotRequired,
        description="Controls extended attribute behavior (on, off, sa, dir).",
    )
    zoned: PropertyValue = Field(default=NotRequired, description="Controls whether filesystem is managed from a zone.")
    available: PropertyValue = Field(
        default=NotRequired,
        description="Amount of space available to dataset and its children.",
    )
    checksum: PropertyValue = Field(
        default=NotRequired,
        description="Controls checksum algorithm used to verify data integrity.",
    )
    compression: PropertyValue = Field(
        default=NotRequired,
        description="Controls compression algorithm used for this dataset.",
    )
    compressratio: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Property showing achieved compression ratio.",
    )
    context: PropertyValue = Field(default=NotRequired, description="SELinux security context for the dataset.")
    copies: PropertyValue = Field(
        default=NotRequired,
        description="Controls number of copies of data stored (1, 2, or 3).",
    )
    createtxg: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Transaction group when dataset was created.",
    )
    creation: PropertyValue = Field(default=NotRequired, description="(READ-ONLY): Timestamp when dataset was created.")
    dedup: PropertyValue = Field(default=NotRequired, description="Controls data deduplication for the dataset.")
    defcontext: PropertyValue = Field(
        default=NotRequired,
        description="SELinux default security context for new files.",
    )
    encryption: PropertyValue = Field(
        default=NotRequired,
        description="Controls encryption cipher suite for the dataset.",
    )
    encryptionroot: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Property showing encryption root dataset.",
    )
    fscontext: PropertyValue = Field(default=NotRequired, description="SELinux filesystem security context.")
    guid: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Globally unique identifier for the dataset.",
    )
    keyformat: PropertyValue = Field(
        default=NotRequired,
        description="Encryption key format (raw, hex, or passphrase).",
    )
    keylocation: PropertyValue = Field(default=NotRequired, description="Location where encryption key is stored.")
    keystatus: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Encryption key status (available/unavailable).",
    )
    logbias: PropertyValue = Field(
        default=NotRequired,
        description="Controls ZIL write behavior (latency or throughput).",
    )
    logicalreferenced: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Logical space referenced by dataset.",
    )
    logicalused: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Logical space used by dataset and descendants.",
    )
    mlslabel: PropertyValue = Field(default=NotRequired, description="Multi-level security label for the dataset.")
    objsetid: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Object set identifier for the dataset.",
    )
    origin: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Snapshot this dataset was cloned from.",
    )
    pbkdf2iters: PropertyValue = Field(
        default=NotRequired,
        description="Number of PBKDF2 iterations for key derivation.",
    )
    prefetch: PropertyValue = Field(
        default=NotRequired,
        description="Controls prefetch behavior (all, metadata, or none).",
    )
    primarycache: PropertyValue = Field(
        default=NotRequired,
        description="Controls primary cache usage (all, metadata, or none).",
    )
    readonly: PropertyValue = Field(default=NotRequired, description="Controls whether dataset can be modified.")
    receive_resume_token: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Token for resuming interrupted zfs receive.",
    )
    redact_snaps: PropertyValue = Field(default=NotRequired, description="(READ-ONLY): List of redaction snapshots.")
    redundant_metadata: PropertyValue = Field(
        default=NotRequired,
        description="Controls redundant metadata storage (all or most).",
    )
    refcompressratio: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Compression ratio for referenced data.",
    )
    referenced: PropertyValue = Field(default=NotRequired, description="(READ-ONLY): Space referenced by this dataset.")
    reservation: PropertyValue = Field(
        default=NotRequired,
        description="Minimum space reserved for dataset and descendants.",
    )
    rootcontext: PropertyValue = Field(default=NotRequired, description="SELinux root directory security context.")
    secondarycache: PropertyValue = Field(
        default=NotRequired,
        description="Controls secondary cache usage (all, metadata, or none).",
    )
    snapdev: PropertyValue = Field(
        default=NotRequired,
        description="Controls snapshot device visibility (hidden or visible).",
    )
    snapshot_count: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Count of snapshots in this dataset.",
    )
    snapshot_limit: PropertyValue = Field(default=NotRequired, description="Maximum number of snapshots allowed.")
    snapshots_changed: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Property indicating snapshot changes.",
    )
    sync: PropertyValue = Field(
        default=NotRequired,
        description="Controls synchronous write behavior (standard, always, disabled).",
    )
    type: PropertyValue | None = Field(
        default=NotRequired,
        description="(READ-ONLY): Type of ZFS dataset (filesystem, volume, etc).",
    )
    used: PropertyValue = Field(default=NotRequired, description="(READ-ONLY): Space used by dataset and descendants.")
    usedbychildren: PropertyValue = Field(default=NotRequired, description="(READ-ONLY): Space used by child datasets.")
    usedbydataset: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Space used by this dataset itself.",
    )
    usedbyrefreservation: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Space used by refreservation.",
    )
    usedbysnapshots: PropertyValue = Field(default=NotRequired, description="(READ-ONLY): Space used by snapshots.")
    written: PropertyValue = Field(
        default=NotRequired,
        description="(READ-ONLY): Space referenced since previous snapshot.",
    )
    refreservation: PropertyValue = Field(default=NotRequired, description="Minimum space reserved for volume itself.")
    volblocksize: PropertyValue = Field(default=NotRequired, description="Block size for volume (typically 8K or 16K).")
    volmode: PropertyValue = Field(default=NotRequired, description="Controls volume mode (default, geom, dev, none).")
    volsize: PropertyValue = Field(default=NotRequired, description="Logical size of the volume.")
    volthreading: PropertyValue = Field(default=NotRequired, description="Controls volume threading behavior.")


class ZFSResourceEntry(BaseModel):
    createtxg: int = Field(description="Transaction group when resource was created.")
    guid: int = Field(description="Globally unique identifier for the resource.")
    name: str = Field(description="The name of the zfs resource.")
    pool: str = Field(description="The name of the zpool that the zfs resouce is associated to.")
    properties: ZFSPropertiesEntry = Field(description="The zfs properties for the resource.")
    type: Literal["FILESYSTEM", "VOLUME"] = Field(description="The type of ZFS resource.")
    user_properties: dict[str, str] | None = Field(
        description="Custom metadata properties with colon-separated names (max 256 chars).",
    )
    children: list | None = Field(description="The children of this zfs resource.")


class ZFSResourceQuery(BaseModel):
    paths: UniqueList[str] = Field(
        default=list(),
        description=(
            "A list of zfs filesystem or volume paths to be queried. In almost all scenarios, you should provide a path"
            " of what you want to query. By providing path(s) here, it allows the API to apply optimizations so that "
            "the requested information is retrieved as efficiently and quickly as possible.\n"
            "\n"
            "Example 1:\n"
            "    {\"paths\": [\"tank/foo\"]} will query the relevant information for this resource only.\n"
            "Example 2:\n"
            "    {\"paths\": [\"tank/foo\", \"dozer/test\"]} will query the relevant information for these resources "
            "only.\n"
            "\n"
            "NOTE:\n"
            "    paths must be non-overlapping if `get_children` is True.\n"
            "    (i.e. this won't work and will raise a validation error)\n"
            "        {\n"
            "            \"paths\": [\"tank/foo1\", \"tank/foo1/foo2\"],\n"
            "            \"get_children\": True\n"
            "        }"
        ),
    )
    properties: list[str] | None = Field(
        default=list(),
        description=(
            "A list of zfs properties to be retrieved. Defaults to an empty list which will return a default set of zfs"
            " properties. Setting this to None will retrieve no zfs properties."
        ),
    )
    get_user_properties: bool = Field(default=False, description="Retrieve user properties for zfs resource(s).")
    get_source: bool = Field(
        default=True,
        exclude_json_schema=True,
        description=(
            "Hidden field to retrieve source information for a zfs property.\n"
            "\n"
            "NOTE: This should only ever be toggled by internal consumers and you should know what you're doing by "
            "toggling this to False."
        ),
    )
    nest_results: bool = Field(
        default=False,
        description=(
            "Return a nested object that associates all children to their respective parents in the filesystem. By "
            "default, each zfs resource is returned as a separate item in the array and is not associated to its "
            "parent."
        ),
    )
    get_children: bool = Field(default=False, description="Retrieve children information for the zfs resource.")


class ZFSResourceQueryArgs(BaseModel):
    data: ZFSResourceQuery = Field(
        default=ZFSResourceQuery(),
        description="Query parameters for retrieving ZFS resource information.",
    )


class ZFSResourceQueryResult(BaseModel):
    result: list[ZFSResourceEntry]
