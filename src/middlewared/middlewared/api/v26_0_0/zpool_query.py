from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel

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
)


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
    guid: int = Field(description="Globally unique identifier for this vdev.")
    state: str = Field(description="Current state (ONLINE, DEGRADED, FAULTED, OFFLINE, UNAVAIL, etc.).")
    stats: ZPoolVdevStats = Field(description="Vdev I/O statistics.")
    children: list["ZPoolVdev"] = Field(description="Child vdevs.")
    top_guid: int | None = Field(default=None, description="GUID of the top-level vdev this belongs to.")


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
    guid: int = Field(description="Globally unique identifier for the pool.")
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


class ZPoolQuery(BaseModel):
    pool_names: list[str] | None = Field(
        default=None,
        description="Pool names to query. None queries all imported pools.",
    )
    properties: list[str] | None = Field(
        default=None,
        description="Property names to retrieve. None returns no properties.",
    )
    topology: bool = Field(default=False, description="Include vdev topology.")
    scan: bool = Field(default=False, description="Include scan/scrub information.")
    expand: bool = Field(default=False, description="Include expansion information.")
    features: bool = Field(default=False, description="Include feature flags.")


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
