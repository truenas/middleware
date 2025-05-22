import typing

from pydantic import Field, PositiveInt

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
)


__all__ = [
    'ReportingEntry', 'ReportingUpdateArgs', 'ReportingUpdateResult', 'ReportingGraphs', 'ReportingGetDataArgs',
    'ReportingGetDataResult', 'ReportingGraphArgs', 'ReportingGeneratePasswordArgs', 'ReportingGeneratePasswordResult',
    'ReportingNetDataGetDataArgs', 'ReportingNetDataGetDataResult', 'ReportingNetdataGraphArgs',
    'ReportingNetdataGraphResult', 'ReportingGraphResult', 'ReportingNetdataGraphs',
]


Timestamp: typing.TypeAlias = PositiveInt


class ReportingEntry(BaseModel):
    id: int
    tier0_days: PositiveInt
    tier1_days: PositiveInt
    tier1_update_interval: PositiveInt


class ReportingGraphIdentifier(BaseModel):
    name: typing.Literal[
        'cpu', 'cputemp', 'disk', 'interface', 'load', 'processes', 'memory', 'uptime', 'arcactualrate', 'arcrate',
        'arcsize', 'arcresult', 'disktemp', 'upscharge', 'upsruntime', 'upsvoltage', 'upscurrent', 'upsfrequency',
        'upsload', 'upstemperature',
    ]
    identifier: NonEmptyString | None = None


class ReportingGraphs(BaseModel):
    name: NonEmptyString
    title: NonEmptyString
    vertical_label: NonEmptyString
    identifiers: list[str] | None


class ReportingNetdataGraphs(ReportingGraphs):
    pass


class ReportingQuery(BaseModel):
    unit: typing.Literal['HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR'] | None = None
    page: PositiveInt = 1
    aggregate: bool = True
    start: Timestamp | None = None
    end: Timestamp | None = None


class ReportingResponseAggregations(BaseModel):
    min: dict
    mean: dict
    max: dict


class ReportingResponse(BaseModel):
    name: NonEmptyString
    identifier: str | None
    data: list
    aggregations: ReportingResponseAggregations
    start: Timestamp
    end: Timestamp
    legend: list[str]


class ReportingGeneratePasswordArgs(BaseModel):
    pass


class ReportingGeneratePasswordResult(BaseModel):
    result: NonEmptyString


class ReportingGetDataArgs(BaseModel):
    graphs: list[ReportingGraphIdentifier] = Field(min_length=1)
    query: ReportingQuery = ReportingQuery()


class ReportingGetDataResult(BaseModel):
    result: list[ReportingResponse]


class ReportingGraphArgs(BaseModel):
    str: NonEmptyString
    query: ReportingQuery = ReportingQuery()


class ReportingGraphResult(BaseModel):
    result: list[ReportingResponse]


class ReportingNetDataGetDataArgs(BaseModel):
    graphs: list[ReportingGraphIdentifier] = Field(min_length=1)
    query: ReportingQuery = ReportingQuery()


class ReportingNetDataGetDataResult(BaseModel):
    result: list[ReportingResponse]


class ReportingNetdataGraphArgs(BaseModel):
    str: NonEmptyString
    query: ReportingQuery = ReportingQuery()


class ReportingNetdataGraphResult(BaseModel):
    result: list[ReportingResponse]


@single_argument_args('reporting_update')
class ReportingUpdateArgs(ReportingEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class ReportingUpdateResult(BaseModel):
    result: ReportingEntry
