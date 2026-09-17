from typing import Annotated, Literal

from pydantic import Field, PositiveInt

from middlewared.api.base import BaseModel, Excluded, NonEmptyString, Private, excluded_field

from .zfs_resource_crud import ZFSResourceCreateProperties

__all__ = (
    "ZPoolScan",
    "ZPoolExpand",
    "ZPoolPropertyValue",
    "ZPoolVdevStats",
    "ZPoolVdev",
    "ZPoolTopology",
    "ZPoolFeature",
    "ZPoolEntry",
    "ZPoolQuery",
    "ZPoolQueryArgs",
    "ZPoolQueryResult",
    "ZPoolQueryAddedEvent",
    "ZPoolQueryChangedEvent",
    "ZPoolQueryRemovedEvent",
    "ZPoolCreateVdev",
    "ZPoolCreateTopology",
    "ZPoolCreateProperties",
    "ZPoolCreateFilesystemProperties",
    "ZPoolCreate",
    "ZPoolCreateArgs",
    "ZPoolCreateResult",
)


def _guids_to_int(vdev: dict) -> None:
    """Older API versions carried vdev guids as integers."""
    vdev["guid"] = int(vdev["guid"])
    if vdev.get("top_guid") is not None:
        vdev["top_guid"] = int(vdev["top_guid"])
    for child in vdev.get("children") or []:
        _guids_to_int(child)


class ZPoolPropertyValue(BaseModel):
    raw: str = Field(description="The raw string representation of the property.")
    source: str | None = Field(
        description="The source from where this property received its value (DEFAULT, LOCAL, NONE, etc.).",
    )
    value: int | float | str | bool | None = Field(description="The native Python value of the property.")


class ZPoolVdevStats(BaseModel):
    timestamp: int = Field(default=0, description="High-resolution timestamp (nanoseconds).")
    allocated: int = Field(default=0, description="Allocated space in bytes.")
    space: int = Field(default=0, description="Total space in bytes.")
    dspace: int = Field(default=0, description="Deflated (compressed) space.")
    pspace: int = Field(default=0, description="Physical space.")
    rsize: int = Field(default=0, description="Replaceable dev size.")
    esize: int = Field(default=0, description="Expandable dev size.")
    read_errors: int = Field(default=0, description="Number of read errors.")
    write_errors: int = Field(default=0, description="Number of write errors.")
    checksum_errors: int = Field(default=0, description="Number of checksum errors.")
    initialize_errors: int = Field(default=0, description="Number of initialize errors.")
    dio_verify_errors: int = Field(default=0, description="Number of direct I/O verify errors.")
    slow_ios: int | None = Field(default=None, description="Number of slow I/Os.")
    self_healed_bytes: int = Field(default=0, description="Self-healed bytes.")
    fragmentation: int = Field(default=0, description="Fragmentation percentage.")
    scan_processed: int = Field(default=0, description="Bytes processed by scan.")
    scan_removing: int = Field(default=0, description="Bytes processed by removal.")
    rebuild_processed: int = Field(default=0, description="Bytes processed by rebuild.")
    noalloc: int = Field(default=0, description="Allocations halted.")
    ops_read: int = Field(default=0, description="Read operations.")
    ops_write: int = Field(default=0, description="Write operations.")
    bytes_read: int = Field(default=0, description="Bytes read.")
    bytes_write: int = Field(default=0, description="Bytes written.")
    configured_ashift: int | None = Field(default=None, description="Configured ashift value.")
    logical_ashift: int | None = Field(default=None, description="Logical ashift value.")
    physical_ashift: int | None = Field(default=None, description="Physical ashift value.")


class ZPoolVdev(BaseModel):
    name: str = Field(description="Vdev name (e.g., 'mirror-0', '/dev/sda1').")
    vdev_type: str = Field(description="Vdev type (e.g., 'mirror', 'raidz1', 'disk').")
    guid: str = Field(description="Globally unique identifier for this vdev, a 64-bit integer as a decimal string.")
    state: str = Field(description="Current state (ONLINE, DEGRADED, FAULTED, OFFLINE, UNAVAIL, etc.).")
    stats: ZPoolVdevStats = Field(description="Vdev I/O statistics.")
    children: list["ZPoolVdev"] = Field(description="Child vdevs.")
    top_guid: str | None = Field(
        default=None,
        description="GUID of the top-level vdev this belongs to, a 64-bit integer as a decimal string.",
    )
    path: str | None = Field(
        default=None,
        description=(
            "Device path stored in the vdev config (e.g. '/dev/disk/by-partuuid/<uuid>'). Unlike `name`, this is "
            "preserved for devices that were missing at pool import time. dRAID distributed spares store their "
            "synthetic spare name as the config path. `null` for interior vdevs (mirror, raidz, draid) that have "
            "no config path."
        ),
    )

    @classmethod
    def to_previous(cls, value):
        _guids_to_int(value)
        return value


class ZPoolTopology(BaseModel):
    data: list[ZPoolVdev] = Field(description="Array of data vdev configurations.")
    log: list[ZPoolVdev] = Field(description="Array of ZFS Intent Log (ZIL) vdev configurations.")
    cache: list[ZPoolVdev] = Field(description="Array of L2ARC cache vdev configurations.")
    spares: list[ZPoolVdev] = Field(description="Array of spare disk configurations.")
    special: list[ZPoolVdev] = Field(description="Array of special vdev configurations for metadata.")
    dedup: list[ZPoolVdev] = Field(description="Array of deduplication table vdev configurations.")


class ZPoolScan(BaseModel):
    function: Literal["RESILVER", "SCRUB"] = Field(description="Type of ZFS pool scan.")
    state: Literal["SCANNING", "FINISHED", "CANCELED"] = Field(description="Current lifecycle state of the scan.")
    start_time: int = Field(description="Scan start time (unix timestamp).")
    end_time: int | None = Field(
        description="Scan end time as unix timestamp (`null` while the scan is still running).",
    )
    percentage: float = Field(description="Scan progress (between 0 and 100%).")
    bytes_to_process: int = Field(description="Total bytes located by scanner.")
    bytes_processed: int = Field(description="Total bytes to scan.")
    bytes_issued: int = Field(description="Issued bytes per scan pass.")
    pause: int | None = Field(description="Pause time as unix timestamp (`null` if the scan is not paused).")
    errors: int = Field(description="Number of scan errors.")
    total_secs_left: int | None = Field(description="Number of seconds left (`null` if the scan is not running).")


class ZPoolExpand(BaseModel):
    state: str = Field(description="Expansion state (e.g., SCANNING, FINISHED).")
    expanding_vdev: int = Field(description="Index of the vdev being expanded.")
    start_time: int = Field(description="Expansion start time (unix timestamp).")
    end_time: int | None = Field(description="Expansion end time as unix timestamp (`null` while expanding).")
    bytes_to_reflow: int = Field(description="Total bytes that need to be reflowed.")
    bytes_reflowed: int = Field(description="Total bytes reflowed so far.")
    waiting_for_resilver: int = Field(description="Non-zero if expansion is waiting for a resilver to complete.")
    total_secs_left: int | None = Field(description="Estimated seconds remaining (`null` if not expanding).")
    percentage: float = Field(description="Expansion progress (between 0 and 100%).")


class ZPoolFeature(BaseModel):
    name: str = Field(description="Feature name.")
    guid: str = Field(description="Feature GUID.")
    description: str = Field(description="Feature description.")
    state: str = Field(description="Feature state.")


class ZPoolEntry(BaseModel):
    id: int | None = Field(
        default=None,
        description=(
            "Database id from `storage.volume`. `null` for the boot pool and for any pool not present in the database."
        ),
    )
    name: str = Field(description="Name of the zpool.")
    guid: str = Field(description="Globally unique identifier for the pool, a 64-bit integer as a decimal string.")
    status: str = Field(description="Current pool status (ONLINE, DEGRADED, FAULTED, OFFLINE, etc.).")
    healthy: bool = Field(description="Whether the pool is in a healthy state.")
    warning: bool = Field(description="Whether the pool has warning conditions.")
    status_code: str | None = Field(
        description="Detailed status code (e.g., OK, ERRATA, FEAT_DISABLED, LOCKED_SED_DISKS).",
    )
    status_detail: str | None = Field(description="Human-readable status description.")
    is_upgraded: bool | None = Field(
        default=None,
        description="Whether every ZFS feature flag on the pool is enabled. `null` for OFFLINE pools.",
    )
    all_sed: bool | None = Field(
        default=None,
        description=(
            "`true` when every disk backing the pool is a Self-Encrypting Drive, `false` when at least one is not. "
            "`null` when the SED status of the pool has not yet been determined or does not apply."
        ),
    )
    properties: dict[str, ZPoolPropertyValue] | None = Field(
        default=None,
        description="Pool properties, keyed by property name.",
    )
    topology: ZPoolTopology | None = Field(default=None, description="Pool vdev topology.")
    scan: ZPoolScan | None = Field(default=None, description="Most recent scrub or resilver information.")
    expand: ZPoolExpand | None = Field(default=None, description="RAIDZ expansion information.")
    features: list[ZPoolFeature] | None = Field(default=None, description="Pool feature flags.")

    @classmethod
    def to_previous(cls, value):
        value["guid"] = int(value["guid"])
        for vdevs in (value.get("topology") or {}).values():
            for vdev in vdevs:
                _guids_to_int(vdev)
        return value


class ZPoolQuery(BaseModel):
    pool_names: list[str] | None = Field(
        default=None,
        description="Pool names to query. `null` queries all imported pools.",
    )
    properties: list[str] | None = Field(
        default=None,
        description="Property names to retrieve. `null` returns no properties.",
    )
    topology: bool = Field(default=False, description="Include vdev topology.")
    scan: bool = Field(default=False, description="Include scan/scrub information.")
    expand: bool = Field(default=False, description="Include expansion information.")
    features: bool = Field(default=False, description="Include feature flags.")
    follow_links: Private[bool] = Field(default=True, description="Resolve device symlinks in the topology.")
    full_path: Private[bool] = Field(default=True, description="Report full device paths in the topology.")


class ZPoolQueryArgs(BaseModel):
    data: ZPoolQuery = Field(default=ZPoolQuery(), description="Query parameters.")


class ZPoolQueryResult(BaseModel):
    result: list[ZPoolEntry]


class ZPoolQueryAddedEvent(BaseModel):
    id: int = Field(description="Database id of the pool.")
    fields: ZPoolEntry = Field(description="Event fields.")


class ZPoolQueryChangedEvent(BaseModel):
    id: int = Field(description="Database id of the pool.")
    fields: ZPoolEntry = Field(description="Event fields.")


class ZPoolQueryRemovedEvent(BaseModel):
    id: int = Field(description="Database id of the pool.")


class ZPoolCreateVdev(BaseModel):
    type: Literal["disk", "mirror", "raidz1", "raidz2", "raidz3", "draid1", "draid2", "draid3"] = Field(
        description=(
            "Vdev type, as `zpool create` names it and as `vdev_type` reports it. `disk` makes every listed disk "
            "its own top-level vdev (a stripe)."
        ),
    )
    disks: list[NonEmptyString] = Field(min_length=1, description="Disk names (e.g. `sda`) making up this vdev.")
    draid_data_disks: int | None = Field(
        default=None,
        description=(
            "Distributed RAID only: data disks per redundancy group. `null` uses every disk left after parity "
            "and spares, at most 8."
        ),
    )
    draid_spare_disks: int = Field(default=0, description="Distributed RAID only: number of distributed spare disks.")


class ZPoolCreateTopology(BaseModel):
    """The vdev grammar of `zpool create`, keyed the way :method:`zpool.query` reports `topology`."""

    data: list[ZPoolCreateVdev] = Field(
        min_length=1,
        description=(
            "Storage vdevs. Unless `force_topology` is set they must share one type and width, and mirrors are "
            "capped at 4 disks and RAIDZ at 15."
        ),
    )
    log: list[ZPoolCreateVdev] = Field(default=[], description="ZFS Intent Log (SLOG) vdevs: `disk` or `mirror`.")
    cache: list[NonEmptyString] = Field(default=[], description="L2ARC cache disks.")
    spares: list[NonEmptyString] = Field(default=[], description="Hot spare disks.")
    special: list[ZPoolCreateVdev] = Field(
        default=[],
        description=(
            "Special allocation class vdevs for metadata and small blocks. dRAID is not permitted, and unless "
            "`force_topology` is set they must be redundant when the data vdevs are."
        ),
    )
    dedup: list[ZPoolCreateVdev] = Field(
        default=[],
        description="Deduplication table vdevs. Same rules as `special`.",
    )


class ZPoolCreateProperties(BaseModel):
    """Pool properties set at creation, as `zpool create -o property=value`. Each field is the native `zpool` \
    property name and values are handed to ZFS verbatim. A field left as null is not sent, so ZFS applies its \
    own default. Fields marked `Private` carry a TrueNAS default that only internal callers may override."""

    autotrim: Literal["on", "off"] | None = Field(
        default=None,
        description="Whether freed blocks are periodically TRIMmed on the pool's disks.",
    )
    comment: str | None = Field(default=None, description="Free-form comment stored with the pool.")
    dedup_table_quota: Literal["auto", "none"] | PositiveInt | None = Field(
        default=None,
        description=(
            "Maximum size of the deduplication table: `auto` sizes it to the dedup vdevs, `none` leaves it "
            "unbounded, or a size in bytes."
        ),
    )
    ashift: Private[Annotated[int, Field(ge=9, le=16)] | None] = Field(
        default=None,
        description="Sector size shift. TrueNAS pins this to 12 (4K sectors).",
    )
    altroot: Private[str | None] = Field(default=None, description="Alternate root under which the pool mounts.")
    cachefile: Private[str | None] = Field(default=None, description="Pool configuration cache file.")
    failmode: Private[Literal["wait", "continue", "panic"] | None] = Field(
        default=None,
        description="Behavior on catastrophic pool failure.",
    )
    autoexpand: Private[Literal["on", "off"] | None] = Field(
        default=None,
        description="Whether the pool grows automatically when its disks are replaced by larger ones.",
    )


class ZPoolCreateFilesystemProperties(ZFSResourceCreateProperties):
    """Root filesystem properties set at creation, as `zpool create -O property=value`. The same native property \
    names :method:`zfs.resource.create` accepts, minus the volume-only ones. A field left as null is not sent, so \
    the TrueNAS defaults apply (`atime=off`, `acltype=posix`, `compression=lz4`, `xattr=sa`, and `recordsize=1M` \
    on dRAID pools)."""

    snapdev: Excluded = excluded_field()
    volblocksize: Excluded = excluded_field()
    volsize: Excluded = excluded_field()


class ZPoolCreate(BaseModel):
    name: NonEmptyString = Field(description="Name for the new pool.")
    topology: ZPoolCreateTopology = Field(
        examples=[
            {
                "data": [{"type": "raidz1", "disks": ["sda", "sdb", "sdc"]}],
                "log": [{"type": "disk", "disks": ["sdd"]}],
                "cache": ["sde"],
                "spares": ["sdf"],
            }
        ],
        description="Physical layout of the pool's vdevs.",
    )
    properties: ZPoolCreateProperties = Field(
        default_factory=ZPoolCreateProperties,
        description="Pool properties to set at creation.",
    )
    filesystem_properties: ZPoolCreateFilesystemProperties = Field(
        default_factory=ZPoolCreateFilesystemProperties,
        description="Properties to set on the pool's root filesystem at creation.",
    )
    force_topology: bool = Field(
        default=False,
        description=(
            "Bypass topology policy validation, like `zpool create -f`. Allows data vdevs that differ in type "
            "or width from the rest of the pool, RAIDZ/mirror vdevs wider than the recommended maximum, and "
            "special or dedup vdevs whose redundancy does not match the data vdevs. Structural requirements "
            "(minimum disks per vdev type, dRAID configuration) and the disk availability checks still apply. "
            "Not permitted on systems with a support entitlement."
        ),
    )
    allow_duplicate_serials: bool = Field(
        default=False,
        description="Whether to allow disks with duplicate serial numbers in the pool.",
    )
    all_sed: bool = Field(
        default=False,
        description="When set, every disk in the pool must be a Self-Encrypting Drive and is provisioned as one.",
    )


class ZPoolCreateArgs(BaseModel):
    data: ZPoolCreate = Field(description="Configuration for the new pool.")


class ZPoolCreateResult(BaseModel):
    result: ZPoolEntry = Field(
        description="The new pool, queried after creation with its topology and the pool properties that were set.",
    )
