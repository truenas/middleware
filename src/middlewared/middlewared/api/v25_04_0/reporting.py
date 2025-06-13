import typing

from pydantic import Field

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
)


__all__ = [
    'ReportingEntry', 'ReportingUpdateArgs', 'ReportingUpdateResult', 'ReportingGraphsItem',
    'ReportingNetdataGetDataArgs', 'ReportingNetdataGraphResult', 'ReportingNetdataGraphArgs',
    'ReportingGeneratePasswordArgs', 'ReportingGeneratePasswordResult', 'ReportingNetdataGraphsItem',
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


class ReportingNetdataGetDataArgs(BaseModel):
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


class ReportingNetdataGraphResult(BaseModel):
    result: list[ReportingGetDataResponse]


class ReportingGraphsItem(BaseModel):
    name: NonEmptyString
    title: NonEmptyString
    vertical_label: NonEmptyString
    identifiers: list[str] | None


class ReportingNetdataGraphsItem(BaseModel):
    name: NonEmptyString
    title: NonEmptyString
    vertical_label: NonEmptyString
    identifiers: list[str] | None


class ReportingNetdataGraphArgs(BaseModel):
    str: NonEmptyString
    query: ReportingQuery = Field(default_factory=lambda: ReportingQuery())


class ReportingGeneratePasswordArgs(BaseModel):
    pass


class ReportingGeneratePasswordResult(BaseModel):
    result: NonEmptyString
