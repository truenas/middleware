from typing import Annotated, Literal

from pydantic import Field, PositiveInt
from truenas_pylibzfs import constants

from middlewared.api.base import BaseModel, Excluded, NonEmptyString, Private, excluded_field

from .zfs_resource_crud import ZFSResourceCreateProperties

__all__ = (
    "ZpoolScan",
    "ZpoolExpand",
    "ZpoolPropertyValue",
    "ZpoolVdevStats",
    "ZpoolVdev",
    "ZpoolTopology",
    "ZpoolFeature",
    "ZpoolEntry",
    "ZpoolQuery",
    "ZpoolQueryArgs",
    "ZpoolQueryResult",
    "ZpoolQueryAddedEvent",
    "ZpoolQueryChangedEvent",
    "ZpoolQueryRemovedEvent",
    "ZpoolCreateVdev",
    "ZpoolCreateTopology",
    "ZpoolCreateProperties",
    "ZpoolCreateFilesystemProperties",
    "ZpoolCreate",
    "ZpoolCreateArgs",
    "ZpoolCreateResult",
)


def _guids_to_int(vdev: dict) -> None:
    """Older API versions carried vdev guids as integers."""
    vdev["guid"] = int(vdev["guid"])
    if vdev.get("top_guid") is not None:
        vdev["top_guid"] = int(vdev["top_guid"])
    for child in vdev.get("children") or []:
        _guids_to_int(child)


class ZpoolPropertyValue(BaseModel):
    raw: str = Field(description="The raw string representation of the property.")
    source: str | None = Field(
        description="The source from where this property received its value (DEFAULT, LOCAL, NONE, etc.).",
    )
    value: int | float | str | bool | None = Field(description="The native Python value of the property.")


class ZpoolVdevStats(BaseModel):
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


class ZpoolVdev(BaseModel):
    name: str = Field(description="Vdev name (e.g., 'mirror-0', '/dev/sda1').")
    vdev_type: str = Field(description="Vdev type (e.g., 'mirror', 'raidz1', 'disk').")
    guid: str = Field(description="Globally unique identifier for this vdev, a 64-bit integer as a decimal string.")
    state: str = Field(description="Current state (ONLINE, DEGRADED, FAULTED, OFFLINE, UNAVAIL, etc.).")
    stats: ZpoolVdevStats = Field(description="Vdev I/O statistics.")
    children: list["ZpoolVdev"] = Field(description="Child vdevs.")
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


class ZpoolTopology(BaseModel):
    data: list[ZpoolVdev] = Field(description="Array of data vdev configurations.")
    log: list[ZpoolVdev] = Field(description="Array of ZFS Intent Log (ZIL) vdev configurations.")
    cache: list[ZpoolVdev] = Field(description="Array of L2ARC cache vdev configurations.")
    spares: list[ZpoolVdev] = Field(description="Array of spare disk configurations.")
    special: list[ZpoolVdev] = Field(description="Array of special vdev configurations for metadata.")
    dedup: list[ZpoolVdev] = Field(description="Array of deduplication table vdev configurations.")


class ZpoolScan(BaseModel):
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


class ZpoolExpand(BaseModel):
    state: str = Field(description="Expansion state (e.g., SCANNING, FINISHED).")
    expanding_vdev: int = Field(description="Index of the vdev being expanded.")
    start_time: int = Field(description="Expansion start time (unix timestamp).")
    end_time: int | None = Field(description="Expansion end time as unix timestamp (`null` while expanding).")
    bytes_to_reflow: int = Field(description="Total bytes that need to be reflowed.")
    bytes_reflowed: int = Field(description="Total bytes reflowed so far.")
    waiting_for_resilver: int = Field(description="Non-zero if expansion is waiting for a resilver to complete.")
    total_secs_left: int | None = Field(description="Estimated seconds remaining (`null` if not expanding).")
    percentage: float = Field(description="Expansion progress (between 0 and 100%).")


class ZpoolFeature(BaseModel):
    name: str = Field(description="Feature name.")
    guid: str = Field(description="Feature GUID.")
    description: str = Field(description="Feature description.")
    state: str = Field(description="Feature state.")


class ZpoolEntry(BaseModel):
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
    properties: dict[str, ZpoolPropertyValue] | None = Field(
        default=None,
        description="Pool properties, keyed by property name.",
    )
    topology: ZpoolTopology | None = Field(default=None, description="Pool vdev topology.")
    scan: ZpoolScan | None = Field(default=None, description="Most recent scrub or resilver information.")
    expand: ZpoolExpand | None = Field(default=None, description="RAIDZ expansion information.")
    features: list[ZpoolFeature] | None = Field(default=None, description="Pool feature flags.")

    @classmethod
    def to_previous(cls, value):
        value["guid"] = int(value["guid"])
        for vdevs in (value.get("topology") or {}).values():
            for vdev in vdevs:
                _guids_to_int(vdev)
        return value


class ZpoolQuery(BaseModel):
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


class ZpoolQueryArgs(BaseModel):
    data: ZpoolQuery = Field(default=ZpoolQuery(), description="Query parameters.")


class ZpoolQueryResult(BaseModel):
    result: list[ZpoolEntry]


class ZpoolQueryAddedEvent(BaseModel):
    id: int = Field(description="Database id of the pool.")
    fields: ZpoolEntry = Field(description="Event fields.")


class ZpoolQueryChangedEvent(BaseModel):
    id: int = Field(description="Database id of the pool.")
    fields: ZpoolEntry = Field(description="Event fields.")


class ZpoolQueryRemovedEvent(BaseModel):
    id: int = Field(description="Database id of the pool.")


class ZpoolCreateVdev(BaseModel):
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


class ZpoolCreateTopology(BaseModel):
    """The vdev grammar of `zpool create`, keyed the way :method:`zpool.query` reports `topology`."""

    data: list[ZpoolCreateVdev] = Field(
        min_length=1,
        description=(
            "Storage vdevs. Unless `force_topology` is set they must share one type and width, and mirrors are "
            f"capped at {constants.MAX_MIRROR_WIDTH} disks and RAIDZ at {constants.MAX_RAIDZ_WIDTH}."
        ),
    )
    log: list[ZpoolCreateVdev] = Field(default=[], description="ZFS Intent Log (SLOG) vdevs: `disk` or `mirror`.")
    cache: list[NonEmptyString] = Field(default=[], description="L2ARC cache disks.")
    spares: list[NonEmptyString] = Field(default=[], description="Hot spare disks.")
    special: list[ZpoolCreateVdev] = Field(
        default=[],
        description=(
            "Special allocation class vdevs for metadata and small blocks. dRAID is not permitted, and unless "
            "`force_topology` is set they must be redundant when the data vdevs are."
        ),
    )
    dedup: list[ZpoolCreateVdev] = Field(
        default=[],
        description="Deduplication table vdevs. Same rules as `special`.",
    )


class ZpoolCreateProperties(BaseModel):
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
            "unbounded, or a size in bytes. Defaults to `auto` when deduplication is enabled on the root filesystem."
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


class ZpoolCreateFilesystemProperties(ZFSResourceCreateProperties):
    """Root filesystem properties set at creation, as `zpool create -O property=value`. The same native property \
    names and values :method:`zfs.resource.create` accepts, minus the volume-only ones. ZFS judges the values \
    before any disk is formatted. A field left as null is not sent, so the TrueNAS defaults apply (`atime=off`, \
    `acltype=posix`, `aclmode=discard`, `aclinherit=discard`, `compression=lz4`, `xattr=sa`, and `recordsize=1M` on \
    dRAID pools)."""

    snapdev: Excluded = excluded_field()
    volblocksize: Excluded = excluded_field()
    volsize: Excluded = excluded_field()


class ZpoolCreate(BaseModel):
    name: NonEmptyString = Field(description="Name for the new pool.")
    topology: ZpoolCreateTopology = Field(
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
    properties: ZpoolCreateProperties = Field(
        default_factory=ZpoolCreateProperties,
        description="Pool properties to set at creation.",
    )
    filesystem_properties: ZpoolCreateFilesystemProperties = Field(
        default_factory=ZpoolCreateFilesystemProperties,
        description="Properties to set on the pool's root filesystem at creation.",
    )
    force_topology: bool = Field(
        default=False,
        description=(
            "Bypass the TrueNAS topology policy: data vdevs that differ in type or width from the rest of the "
            "pool, mirror and RAIDZ vdevs wider than the recommended maximum, and special or dedup vdevs with less "
            "redundancy than the data vdevs. Unlike `zpool create -f` it never bypasses the disk availability "
            "checks, and the structural requirements (minimum disks per vdev type, dRAID configuration) still "
            "apply. Not permitted on systems with a support entitlement."
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


class ZpoolCreateArgs(BaseModel):
    data: ZpoolCreate = Field(description="Configuration for the new pool.")


class ZpoolCreateResult(BaseModel):
    result: ZpoolEntry = Field(
        description="The new pool, queried after creation with its topology and the pool properties that were set.",
    )
