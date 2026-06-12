import typing

from pydantic import Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    NonEmptyString,
    excluded_field,
    single_argument_args,
    single_argument_result,
)

__all__ = [
    'ReportingEntry', 'ReportingUpdateArgs', 'ReportingUpdateResult', 'ReportingGraphsItem',
    'ReportingNetdataGetDataArgs', 'ReportingNetdataGraphResult', 'ReportingNetdataGraphArgs',
    'ReportingGeneratePasswordArgs', 'ReportingGeneratePasswordResult', 'ReportingRealtimeEventSourceArgs',
    'ReportingRealtimeEventSourceEvent', 'ReportingGetDataArgs', 'ReportingGetDataResult', 'ReportingGraphArgs',
    'ReportingGraphResult', 'ReportingNetdataGetDataResult', 'ReportingNetdataGraphsItem',
]


class ReportingEntry(BaseModel):
    id: int = Field(description="Unique identifier for the reporting configuration.")
    tier0_days: int = Field(ge=1, description="Number of days to keep high-resolution reporting data.")
    tier1_days: int = Field(ge=1, description="Number of days to keep lower-resolution aggregated reporting data.")
    tier1_update_interval: int = Field(ge=1, description="Interval in seconds for updating aggregated tier1 data.")


@single_argument_args('reporting_update')
class ReportingUpdateArgs(ReportingEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class ReportingUpdateResult(BaseModel):
    result: ReportingEntry = Field(description="The updated reporting configuration.")


timestamp: typing.TypeAlias = typing.Annotated[int, Field(gt=0)]


class ReportingQuery(BaseModel):
    unit: typing.Literal['HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR'] | None = Field(
        default=None,
        description="Time unit for data aggregation. `null` for default aggregation.",
    )
    page: int = Field(default=1, ge=1, description="Page number for paginated results.")
    aggregate: bool = Field(default=True, description="Whether to return aggregated data or raw data points.")
    start: timestamp | None = Field(
        default=None,
        description="Start timestamp for the data range. `null` for default start time.",
    )
    end: timestamp | None = Field(
        default=None,
        description="End timestamp for the data range. `null` for current time.",
    )


class GraphIdentifier(BaseModel):
    name: typing.Literal[
        'cpu', 'cputemp', 'disk', 'interface', 'load', 'processes', 'memory', 'uptime',
        'arcsize', 'disktemp', 'upscharge', 'upsruntime', 'upsvoltage', 'upscurrent', 'upsfrequency',
        'upsload', 'upstemperature',
    ] = Field(
        description=(
            "Type of performance metric to retrieve.\n"
            "\n"
            "* `cpu`: CPU usage statistics\n"
            "* `cputemp`: CPU temperature readings\n"
            "* `disk`: Disk I/O statistics\n"
            "* `interface`: Network interface statistics\n"
            "* `load`: System load averages\n"
            "* `processes`: Process count and statistics\n"
            "* `memory`: Memory usage statistics\n"
            "* `uptime`: System uptime\n"
            "* `arcsize`: ZFS ARC cache size\n"
            "* `disktemp`: Disk temperature readings\n"
            "* `upscharge`: UPS battery charge level\n"
            "* `upsruntime`: UPS estimated runtime\n"
            "* `upsvoltage`: UPS voltage readings\n"
            "* `upscurrent`: UPS current readings\n"
            "* `upsfrequency`: UPS frequency readings\n"
            "* `upsload`: UPS load percentage\n"
            "* `upstemperature`: UPS temperature readings"
        ),
    )
    identifier: NonEmptyString | None = Field(
        default=None,
        description=(
            "Specific instance identifier for the metric (e.g., device name, interface name). `null` for system-wide "
            "metrics."
        ),
    )


_REMOVED_GRAPH_NAMES = frozenset({'arcrate', 'arcactualrate', 'arcresult'})


class ReportingNetdataGetDataArgs(BaseModel):
    graphs: list[GraphIdentifier] = Field(
        min_length=1,
        description="Array of graph identifiers specifying which metrics to retrieve.",
    )
    query: ReportingQuery = Field(
        default_factory=lambda: ReportingQuery(),
        description="Query parameters for filtering and formatting the returned data.",
    )

    @classmethod
    def from_previous(cls, value):
        value['graphs'] = [g for g in value['graphs'] if g.get('name') not in _REMOVED_GRAPH_NAMES]
        return value


class Aggregations(BaseModel):
    min: dict = Field(description="Minimum values for each data series over the time period.")
    mean: dict = Field(description="Average values for each data series over the time period.")
    max: dict = Field(description="Maximum values for each data series over the time period.")


class ReportingGetDataResponse(BaseModel):
    name: NonEmptyString = Field(description="Name of the performance metric.")
    identifier: str | None = Field(
        description="Specific instance identifier for the metric. `null` for system-wide metrics.",
    )
    data: list = Field(description="Array of time-series data points for the requested time period.")
    aggregations: Aggregations | None = Field(description="Statistical aggregations of the data over the time period.")
    start: timestamp = Field(description="Actual start timestamp of the returned data.")
    end: timestamp = Field(description="Actual end timestamp of the returned data.")
    legend: list[str] = Field(description="Array of labels describing each data series in the results.")


class ReportingNetdataGraphResult(BaseModel):
    result: list[ReportingGetDataResponse] = Field(
        description="Array of performance data responses for each requested graph.",
    )


class ReportingGraphsItem(BaseModel):
    name: NonEmptyString = Field(description="Unique name identifier for the graph type.")
    title: NonEmptyString = Field(description="Human-readable title for display purposes.")
    vertical_label: NonEmptyString = Field(description="Label for the vertical (Y) axis of the graph.")
    identifiers: list[str] | None = Field(
        description="Array of available instance identifiers for this graph type. `null` if not applicable.",
    )


class ReportingNetdataGraphsItem(BaseModel):
    name: NonEmptyString = Field(description="Unique name identifier for the netdata graph type.")
    title: NonEmptyString = Field(description="Human-readable title for display purposes.")
    vertical_label: NonEmptyString = Field(description="Label for the vertical (Y) axis of the graph.")
    identifiers: list[str] | None = Field(
        description="Array of available instance identifiers for this graph type. `null` if not applicable.",
    )


class ReportingNetdataGraphArgs(BaseModel):
    str: NonEmptyString = Field(description="String identifier for the specific graph to retrieve.")
    query: ReportingQuery = Field(
        default_factory=lambda: ReportingQuery(),
        description="Query parameters for filtering and formatting the returned data.",
    )


class ReportingGeneratePasswordArgs(BaseModel):
    pass


class ReportingGeneratePasswordResult(BaseModel):
    result: NonEmptyString = Field(description="The generated password for reporting access.")


class ReportingRealtimeEventSourceArgs(BaseModel):
    interval: int = Field(default=2, ge=2, description="Interval in seconds between real-time data updates.")


@single_argument_result
class ReportingRealtimeEventSourceEvent(BaseModel):
    cpu: dict = Field(description="CPU performance metrics for real-time monitoring.")
    disks: "ReportingRealtimeEventSourceEventDisks" = Field(
        description="Disk performance metrics for real-time monitoring.",
    )
    interfaces: dict = Field(description="Network interface statistics for real-time monitoring.")
    memory: "ReportingRealtimeEventSourceEventMemory" = Field(
        description="Memory usage metrics for real-time monitoring.",
    )
    zfs: "ReportingRealtimeEventSourceEventZFS" = Field(description="ZFS performance metrics for real-time monitoring.")
    pools: dict = Field(description="Storage pool statistics for real-time monitoring.")


class ReportingRealtimeEventSourceEventDisks(BaseModel):
    busy: float = Field(description="Percentage of time the disk was busy servicing requests.")
    read_bytes: float = Field(description="Bytes read from disk per second.")
    write_bytes: float = Field(description="Bytes written to disk per second.")
    read_ops: float = Field(description="Read operations per second.")
    write_ops: float = Field(description="Write operations per second.")


class ReportingRealtimeEventSourceEventMemory(BaseModel):
    arc_size: int = Field(description="Current size of the ZFS ARC cache in bytes.")
    arc_free_memory: int = Field(description="Amount of free memory in the ZFS ARC cache in bytes.")
    arc_available_memory: int = Field(description="Amount of memory available to the ZFS ARC cache in bytes.")
    physical_memory_total: int = Field(description="Total physical memory in the system in bytes.")
    physical_memory_available: int = Field(description="Available physical memory in the system in bytes.")


class ReportingRealtimeEventSourceEventZFS(BaseModel):
    demand_accesses_per_second: int = Field(description="Total ZFS ARC demand accesses per second.")
    demand_data_accesses_per_second: int = Field(description="ZFS ARC data demand accesses per second.")
    demand_metadata_accesses_per_second: int = Field(description="ZFS ARC metadata demand accesses per second.")
    demand_data_hits_per_second: int = Field(description="ZFS ARC data demand hits per second.")
    demand_data_io_hits_per_second: int = Field(description="ZFS ARC data demand I/O hits per second.")
    demand_data_misses_per_second: int = Field(description="ZFS ARC data demand misses per second.")
    demand_data_hit_percentage: int = Field(description="Percentage of ZFS ARC data demand requests that were hits.")
    demand_data_io_hit_percentage: int = Field(
        description="Percentage of ZFS ARC data demand I/O requests that were hits.",
    )
    demand_data_miss_percentage: int = Field(description="Percentage of ZFS ARC data demand requests that were misses.")
    demand_metadata_hits_per_second: int = Field(description="ZFS ARC metadata demand hits per second.")
    demand_metadata_io_hits_per_second: int = Field(description="ZFS ARC metadata demand I/O hits per second.")
    demand_metadata_misses_per_second: int = Field(description="ZFS ARC metadata demand misses per second.")
    demand_metadata_hit_percentage: int = Field(
        description="Percentage of ZFS ARC metadata demand requests that were hits.",
    )
    demand_metadata_io_hit_percentage: int = Field(
        description="Percentage of ZFS ARC metadata demand I/O requests that were hits.",
    )
    demand_metadata_miss_percentage: int = Field(
        description="Percentage of ZFS ARC metadata demand requests that were misses.",
    )
    l2arc_hits_per_second: int = Field(description="ZFS L2ARC hits per second.")
    l2arc_misses_per_second: int = Field(description="ZFS L2ARC misses per second.")
    total_l2arc_accesses_per_second: int = Field(description="Total ZFS L2ARC accesses per second.")
    l2arc_access_hit_percentage: int = Field(description="Percentage of ZFS L2ARC accesses that were hits.")
    l2arc_miss_percentage: int = Field(description="Percentage of ZFS L2ARC accesses that were misses.")
    bytes_read_per_second_from_the_l2arc: int = Field(description="Bytes read per second from the ZFS L2ARC cache.")
    bytes_written_per_second_to_the_l2arc: int = Field(description="Bytes written per second to the ZFS L2ARC cache.")


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
