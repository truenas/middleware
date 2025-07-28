import typing

from pydantic import Field

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
    single_argument_result,
)


__all__ = [
    'ReportingEntry', 'ReportingUpdateArgs', 'ReportingUpdateResult', 'ReportingGraphsItem', 'ReportingNetdataGetDataArgs',
    'ReportingNetdataGraphResult', 'ReportingNetdataGraphArgs', 'ReportingGeneratePasswordArgs',
    'ReportingGeneratePasswordResult', 'ReportingRealtimeEventSourceArgs', 'ReportingRealtimeEventSourceEvent',
    'ReportingGetDataArgs', 'ReportingGetDataResult', 'ReportingGraphArgs', 'ReportingGraphResult',
    'ReportingNetdataGetDataResult', 'ReportingNetdataGraphsItem',
]


class ReportingEntry(BaseModel):
    id: int
    """Unique identifier for the reporting configuration."""
    tier0_days: int = Field(ge=1)
    """Number of days to keep high-resolution reporting data."""
    tier1_days: int = Field(ge=1)
    """Number of days to keep lower-resolution aggregated reporting data."""
    tier1_update_interval: int = Field(ge=1)
    """Interval in seconds for updating aggregated tier1 data."""


@single_argument_args('reporting_update')
class ReportingUpdateArgs(ReportingEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class ReportingUpdateResult(BaseModel):
    result: ReportingEntry
    """The updated reporting configuration."""


timestamp: typing.TypeAlias = typing.Annotated[int, Field(gt=0)]


class ReportingQuery(BaseModel):
    unit: typing.Literal['HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR'] | None = None
    """Time unit for data aggregation. `null` for default aggregation."""
    page: int = Field(default=1, ge=1)
    """Page number for paginated results."""
    aggregate: bool = True
    """Whether to return aggregated data or raw data points."""
    start: timestamp | None = None
    """Start timestamp for the data range. `null` for default start time."""
    end: timestamp | None = None
    """End timestamp for the data range. `null` for current time."""


class GraphIdentifier(BaseModel):
    name: typing.Literal[
        'cpu', 'cputemp', 'disk', 'interface', 'load', 'processes', 'memory', 'uptime', 'arcactualrate', 'arcrate',
        'arcsize', 'arcresult', 'disktemp', 'upscharge', 'upsruntime', 'upsvoltage', 'upscurrent', 'upsfrequency',
        'upsload', 'upstemperature',
    ]
    """Type of performance metric to retrieve.

    * `cpu`: CPU usage statistics
    * `cputemp`: CPU temperature readings
    * `disk`: Disk I/O statistics
    * `interface`: Network interface statistics
    * `load`: System load averages
    * `processes`: Process count and statistics
    * `memory`: Memory usage statistics
    * `uptime`: System uptime
    * `arcactualrate`: ZFS ARC actual hit rate
    * `arcrate`: ZFS ARC hit rate
    * `arcsize`: ZFS ARC cache size
    * `arcresult`: ZFS ARC operation results
    * `disktemp`: Disk temperature readings
    * `upscharge`: UPS battery charge level
    * `upsruntime`: UPS estimated runtime
    * `upsvoltage`: UPS voltage readings
    * `upscurrent`: UPS current readings
    * `upsfrequency`: UPS frequency readings
    * `upsload`: UPS load percentage
    * `upstemperature`: UPS temperature readings
    """
    identifier: NonEmptyString | None = None
    """Specific instance identifier for the metric (e.g., device name, interface name). `null` for system-wide metrics."""


class ReportingNetdataGetDataArgs(BaseModel):
    graphs: list[GraphIdentifier] = Field(min_length=1)
    """Array of graph identifiers specifying which metrics to retrieve."""
    query: ReportingQuery = Field(default_factory=lambda: ReportingQuery())
    """Query parameters for filtering and formatting the returned data."""


class Aggregations(BaseModel):
    min: dict
    """Minimum values for each data series over the time period."""
    mean: dict
    """Average values for each data series over the time period."""
    max: dict
    """Maximum values for each data series over the time period."""


class ReportingGetDataResponse(BaseModel):
    name: NonEmptyString
    """Name of the performance metric."""
    identifier: str | None
    """Specific instance identifier for the metric. `null` for system-wide metrics."""
    data: list
    """Array of time-series data points for the requested time period."""
    aggregations: Aggregations
    """Statistical aggregations of the data over the time period."""
    start: timestamp
    """Actual start timestamp of the returned data."""
    end: timestamp
    """Actual end timestamp of the returned data."""
    legend: list[str]
    """Array of labels describing each data series in the results."""


class ReportingNetdataGraphResult(BaseModel):
    result: list[ReportingGetDataResponse]
    """Array of performance data responses for each requested graph."""


class ReportingGraphsItem(BaseModel):
    name: NonEmptyString
    """Unique name identifier for the graph type."""
    title: NonEmptyString
    """Human-readable title for display purposes."""
    vertical_label: NonEmptyString
    """Label for the vertical (Y) axis of the graph."""
    identifiers: list[str] | None
    """Array of available instance identifiers for this graph type. `null` if not applicable."""


class ReportingNetdataGraphsItem(BaseModel):
    name: NonEmptyString
    """Unique name identifier for the netdata graph type."""
    title: NonEmptyString
    """Human-readable title for display purposes."""
    vertical_label: NonEmptyString
    """Label for the vertical (Y) axis of the graph."""
    identifiers: list[str] | None
    """Array of available instance identifiers for this graph type. `null` if not applicable."""


class ReportingNetdataGraphArgs(BaseModel):
    str: NonEmptyString
    """String identifier for the specific graph to retrieve."""
    query: ReportingQuery = Field(default_factory=lambda: ReportingQuery())
    """Query parameters for filtering and formatting the returned data."""


class ReportingGeneratePasswordArgs(BaseModel):
    pass


class ReportingGeneratePasswordResult(BaseModel):
    result: NonEmptyString
    """The generated password for reporting access."""


class ReportingRealtimeEventSourceArgs(BaseModel):
    interval: int = Field(default=2, ge=2)
    """Interval in seconds between real-time data updates."""


@single_argument_result
class ReportingRealtimeEventSourceEvent(BaseModel):
    cpu: dict
    """CPU performance metrics for real-time monitoring."""
    disls: "ReportingRealtimeEventSourceEventDisks"
    """Disk performance metrics for real-time monitoring."""
    interfaces: dict
    """Network interface statistics for real-time monitoring."""
    memory: "ReportingRealtimeEventSourceEventMemory"
    """Memory usage metrics for real-time monitoring."""
    zfs: "ReportingRealtimeEventSourceEventZFS"
    """ZFS performance metrics for real-time monitoring."""
    pools: dict
    """Storage pool statistics for real-time monitoring."""


class ReportingRealtimeEventSourceEventDisks(BaseModel):
    busy: float
    """Percentage of time the disk was busy servicing requests."""
    read_bytes: float
    """Bytes read from disk per second."""
    write_bytes: float
    """Bytes written to disk per second."""
    read_ops: float
    """Read operations per second."""
    write_ops: float
    """Write operations per second."""


class ReportingRealtimeEventSourceEventMemory(BaseModel):
    arc_size: int
    """Current size of the ZFS ARC cache in bytes."""
    arc_free_memory: int
    """Amount of free memory in the ZFS ARC cache in bytes."""
    arc_available_memory: int
    """Amount of memory available to the ZFS ARC cache in bytes."""
    physical_memory_total: int
    """Total physical memory in the system in bytes."""
    physical_memory_available: int
    """Available physical memory in the system in bytes."""


class ReportingRealtimeEventSourceEventZFS(BaseModel):
    demand_accesses_per_second: int
    """Total ZFS ARC demand accesses per second."""
    demand_data_accesses_per_second: int
    """ZFS ARC data demand accesses per second."""
    demand_metadata_accesses_per_second: int
    """ZFS ARC metadata demand accesses per second."""
    demand_data_hits_per_second: int
    """ZFS ARC data demand hits per second."""
    demand_data_io_hits_per_second: int
    """ZFS ARC data demand I/O hits per second."""
    demand_data_misses_per_second: int
    """ZFS ARC data demand misses per second."""
    demand_data_hit_percentage: int
    """Percentage of ZFS ARC data demand requests that were hits."""
    demand_data_io_hit_percentage: int
    """Percentage of ZFS ARC data demand I/O requests that were hits."""
    demand_data_miss_percentage: int
    """Percentage of ZFS ARC data demand requests that were misses."""
    demand_metadata_hits_per_second: int
    """ZFS ARC metadata demand hits per second."""
    demand_metadata_io_hits_per_second: int
    """ZFS ARC metadata demand I/O hits per second."""
    demand_metadata_misses_per_second: int
    """ZFS ARC metadata demand misses per second."""
    demand_metadata_hit_percentage: int
    """Percentage of ZFS ARC metadata demand requests that were hits."""
    demand_metadata_io_hit_percentage: int
    """Percentage of ZFS ARC metadata demand I/O requests that were hits."""
    demand_metadata_miss_percentage: int
    """Percentage of ZFS ARC metadata demand requests that were misses."""
    l2arc_hits_per_second: int
    """ZFS L2ARC hits per second."""
    l2arc_misses_per_second: int
    """ZFS L2ARC misses per second."""
    total_l2arc_accesses_per_second: int
    """Total ZFS L2ARC accesses per second."""
    l2arc_access_hit_percentage: int
    """Percentage of ZFS L2ARC accesses that were hits."""
    l2arc_miss_percentage: int
    """Percentage of ZFS L2ARC accesses that were misses."""
    bytes_read_per_second_from_the_l2arc: int
    """Bytes read per second from the ZFS L2ARC cache."""
    bytes_written_per_second_to_the_l2arc: int
    """Bytes written per second to the ZFS L2ARC cache."""


class ReportingGetDataArgs(ReportingNetdataGetDataArgs):
    pass


class ReportingGetDataResult(ReportingNetdataGraphResult):
    pass


class ReportingGraphArgs(ReportingNetdataGraphArgs):
    pass


class ReportingGraphResult(ReportingNetdataGraphResult):
    pass


class ReportingNetdataGetDataResult(ReportingNetdataGraphResult):
    pass
