from typing import Literal

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
)


class ZPoolPropertyValue(BaseModel):
    raw: str
    """The raw string representation of the property."""
    source: str | None
    """The source from where this property received its value (DEFAULT, LOCAL, NONE, etc.)."""
    value: int | float | str | bool | None
    """The native Python value of the property."""


class ZPoolVdevStats(BaseModel):
    timestamp: int = 0
    """High-resolution timestamp (nanoseconds)."""
    allocated: int = 0
    """Allocated space in bytes."""
    space: int = 0
    """Total space in bytes."""
    dspace: int = 0
    """Deflated (compressed) space."""
    pspace: int = 0
    """Physical space."""
    rsize: int = 0
    """Replaceable dev size."""
    esize: int = 0
    """Expandable dev size."""
    read_errors: int = 0
    """Number of read errors."""
    write_errors: int = 0
    """Number of write errors."""
    checksum_errors: int = 0
    """Number of checksum errors."""
    initialize_errors: int = 0
    """Number of initialize errors."""
    dio_verify_errors: int = 0
    """Number of direct I/O verify errors."""
    slow_ios: int | None = None
    """Number of slow I/Os."""
    self_healed_bytes: int = 0
    """Self-healed bytes."""
    fragmentation: int = 0
    """Fragmentation percentage."""
    scan_processed: int = 0
    """Bytes processed by scan."""
    scan_removing: int = 0
    """Bytes processed by removal."""
    rebuild_processed: int = 0
    """Bytes processed by rebuild."""
    noalloc: int = 0
    """Allocations halted."""
    ops_read: int = 0
    """Read operations."""
    ops_write: int = 0
    """Write operations."""
    bytes_read: int = 0
    """Bytes read."""
    bytes_write: int = 0
    """Bytes written."""
    configured_ashift: int | None = None
    """Configured ashift value."""
    logical_ashift: int | None = None
    """Logical ashift value."""
    physical_ashift: int | None = None
    """Physical ashift value."""


class ZPoolVdev(BaseModel):
    name: str
    """Vdev name (e.g., 'mirror-0', '/dev/sda1')."""
    vdev_type: str
    """Vdev type (e.g., 'mirror', 'raidz1', 'disk')."""
    guid: int
    """Globally unique identifier for this vdev."""
    state: str
    """Current state (ONLINE, DEGRADED, FAULTED, OFFLINE, UNAVAIL, etc.)."""
    stats: ZPoolVdevStats
    """Vdev I/O statistics."""
    children: list["ZPoolVdev"]
    """Child vdevs."""
    top_guid: int | None = None
    """GUID of the top-level vdev this belongs to."""


class ZPoolTopology(BaseModel):
    data: list[ZPoolVdev]
    """Array of data vdev configurations."""
    log: list[ZPoolVdev]
    """Array of ZFS Intent Log (ZIL) vdev configurations."""
    cache: list[ZPoolVdev]
    """Array of L2ARC cache vdev configurations."""
    spares: list[ZPoolVdev]
    """Array of spare disk configurations."""
    stripe: list[ZPoolVdev]
    """Array of stripe (single-disk) vdev configurations."""
    special: list[ZPoolVdev]
    """Array of special vdev configurations for metadata."""
    dedup: list[ZPoolVdev]
    """Array of deduplication table vdev configurations."""


class ZPoolScan(BaseModel):
    function: Literal["RESILVER", "SCRUB"]
    """Type of ZFS pool scan."""
    state: Literal["SCANNING", "FINISHED", "CANCELED"]
    """Current lifecycle state of the scan."""
    start_time: int
    """Scan start time (unix timestamp)."""
    end_time: int | None
    """Scan end time as unix timestamp (`null` while the scan is still running)."""
    percentage: float
    """Scan progress (between 0 and 100%)."""
    bytes_to_process: int
    """Total bytes located by scanner."""
    bytes_processed: int
    """Total bytes to scan."""
    bytes_issued: int
    """Issued bytes per scan pass."""
    pause: int | None
    """Pause time as unix timestamp (`null` if the scan is not paused)."""
    errors: int
    """Number of scan errors."""
    total_secs_left: int | None
    """Number of seconds left (`null` if the scan is not running)."""


class ZPoolExpand(BaseModel):
    state: str
    """Expansion state (e.g., SCANNING, FINISHED)."""
    expanding_vdev: int
    """Index of the vdev being expanded."""
    start_time: int
    """Expansion start time (unix timestamp)."""
    end_time: int | None
    """Expansion end time as unix timestamp (`null` while expanding)."""
    bytes_to_reflow: int
    """Total bytes that need to be reflowed."""
    bytes_reflowed: int
    """Total bytes reflowed so far."""
    waiting_for_resilver: int
    """Non-zero if expansion is waiting for a resilver to complete."""
    total_secs_left: int | None
    """Estimated seconds remaining (`null` if not expanding)."""
    percentage: float
    """Expansion progress (between 0 and 100%)."""


class ZPoolFeature(BaseModel):
    name: str
    """Feature name."""
    guid: str
    """Feature GUID."""
    description: str
    """Feature description."""
    state: str
    """Feature state."""


class ZPoolEntry(BaseModel):
    name: str
    """Name of the zpool."""
    guid: int
    """Globally unique identifier for the pool."""
    status: str
    """Current pool status (ONLINE, DEGRADED, FAULTED, OFFLINE, etc.)."""
    healthy: bool
    """Whether the pool is in a healthy state."""
    warning: bool
    """Whether the pool has warning conditions."""
    status_code: str | None
    """Detailed status code (e.g., OK, ERRATA, FEAT_DISABLED, LOCKED_SED_DISKS)."""
    status_detail: str | None
    """Human-readable status description."""
    properties: dict[str, ZPoolPropertyValue] | None = None
    """Pool properties, keyed by property name."""
    topology: ZPoolTopology | None = None
    """Pool vdev topology."""
    scan: ZPoolScan | None = None
    """Most recent scrub or resilver information."""
    expand: ZPoolExpand | None = None
    """RAIDZ expansion information."""
    features: list[ZPoolFeature] | None = None
    """Pool feature flags."""


class ZPoolQuery(BaseModel):
    pool_names: list[str] | None = None
    """Pool names to query. None queries all imported pools."""
    properties: list[str] | None = None
    """Property names to retrieve. None returns no properties."""
    topology: bool = False
    """Include vdev topology."""
    scan: bool = False
    """Include scan/scrub information."""
    expand: bool = False
    """Include expansion information."""
    features: bool = False
    """Include feature flags."""


class ZPoolQueryArgs(BaseModel):
    data: ZPoolQuery = ZPoolQuery()
    """Query parameters."""


class ZPoolQueryResult(BaseModel):
    result: list[ZPoolEntry]
