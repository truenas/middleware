import typing

from pydantic import Field

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
    single_argument_result,
)


__all__ = [
    'ReportingEntry', 'ReportingUpdateArgs', 'ReportingUpdateResult', 'ReportingGraph', 'ReportingGetDataArgs',
    'ReportingGetDataResult', 'ReportingGraphArgs', 'ReportingGeneratePasswordArgs', 'ReportingGeneratePasswordResult',
    'ReportingRealtimeEventSourceArgs', 'ReportingRealtimeEventSourceEvent',
]


class ReportingEntry(BaseModel):
    id: int
    tier0_days: int = Field(ge=1)
    tier1_days: int = Field(ge=1)
    tier1_update_interval: int = Field(ge=1)


@single_argument_args('reporting_update')
class ReportingUpdateArgs(ReportingEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class ReportingUpdateResult(BaseModel):
    result: ReportingEntry


timestamp: typing.TypeAlias = typing.Annotated[int, Field(gt=0)]


class ReportingQuery(BaseModel):
    unit: typing.Literal['HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR'] | None = None
    page: int = Field(default=1, ge=1)
    aggregate: bool = True
    start: timestamp | None = None
    end: timestamp | None = None


class GraphIdentifier(BaseModel):
    name: typing.Literal[
        'cpu', 'cputemp', 'disk', 'interface', 'load', 'processes', 'memory', 'uptime', 'arcactualrate', 'arcrate',
        'arcsize', 'arcresult', 'disktemp', 'upscharge', 'upsruntime', 'upsvoltage', 'upscurrent', 'upsfrequency',
        'upsload', 'upstemperature',
    ]
    identifier: NonEmptyString | None = None


class ReportingGetDataArgs(BaseModel):
    graphs: list[GraphIdentifier] = Field(min_length=1)
    query: ReportingQuery = Field(default_factory=lambda: ReportingQuery())


class Aggregations(BaseModel):
    min: dict
    mean: dict
    max: dict


class ReportingGetDataResponse(BaseModel):
    name: NonEmptyString
    identifier: str | None
    data: list
    aggregations: Aggregations
    start: timestamp
    end: timestamp
    legend: list[str]


class ReportingGetDataResult(BaseModel):
    result: list[ReportingGetDataResponse]


class ReportingGraph(BaseModel):
    name: NonEmptyString
    title: NonEmptyString
    vertical_label: NonEmptyString
    identifiers: list[str] | None


class ReportingGraphArgs(BaseModel):
    str: NonEmptyString
    query: ReportingQuery = Field(default_factory=lambda: ReportingQuery())


class ReportingGeneratePasswordArgs(BaseModel):
    pass


class ReportingGeneratePasswordResult(BaseModel):
    result: NonEmptyString


class ReportingRealtimeEventSourceArgs(BaseModel):
    interval: int = Field(default=2, ge=2)


@single_argument_result
class ReportingRealtimeEventSourceEvent(BaseModel):
    cpu: dict
    disls: "ReportingRealtimeEventSourceEventDisks"
    interfaces: dict
    memory: "ReportingRealtimeEventSourceEventMemory"
    zfs: "ReportingRealtimeEventSourceEventZFS"
    pools: dict


class ReportingRealtimeEventSourceEventDisks(BaseModel):
    busy: float
    read_bytes: float
    write_bytes: float
    read_ops: float
    write_ops: float


class ReportingRealtimeEventSourceEventMemory(BaseModel):
    arc_size: int
    arc_free_memory: int
    arc_available_memory: int
    physical_memory_total: int
    physical_memory_available: int


class ReportingRealtimeEventSourceEventZFS(BaseModel):
    demand_accesses_per_second: int
    demand_data_accesses_per_second: int
    demand_metadata_accesses_per_second: int
    demand_data_hits_per_second: int
    demand_data_io_hits_per_second: int
    demand_data_misses_per_second: int
    demand_data_hit_percentage: int
    demand_data_io_hit_percentage: int
    demand_data_miss_percentage: int
    demand_metadata_hits_per_second: int
    demand_metadata_io_hits_per_second: int
    demand_metadata_misses_per_second: int
    demand_metadata_hit_percentage: int
    demand_metadata_io_hit_percentage: int
    demand_metadata_miss_percentage: int
    l2arc_hits_per_second: int
    l2arc_misses_per_second: int
    total_l2arc_accesses_per_second: int
    l2arc_access_hit_percentage: int
    l2arc_miss_percentage: int
    bytes_read_per_second_from_the_l2arc: int
    bytes_written_per_second_to_the_l2arc: int
