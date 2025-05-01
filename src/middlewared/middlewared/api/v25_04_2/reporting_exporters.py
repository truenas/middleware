from typing import Annotated, Literal, TypeAlias

from pydantic import ConfigDict, Field

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args
)


__all__ = [
    'ReportingExporterEntry', 'ReportingExporterCreateArgs', 'ReportingExporterCreateResult', 'GraphiteExporter',
    'ReportingExporterUpdateArgs', 'ReportingExporterUpdateResult', 'ReportingExporterDeleteArgs',
    'ReportingExporterDeleteResult', 'ReportingExporterSchemasArgs', 'ReportingExporterSchemasResult',
]


# Exporter models

class GraphiteExporter(BaseModel):
    exporter_type: Literal['GRAPHITE']
    destination_ip: NonEmptyString
    destination_port: int = Field(ge=1, le=65535)
    prefix: str = 'scale'
    namespace: NonEmptyString
    update_every: int = Field(default=1, ge=1)
    buffer_on_failures: int = Field(default=10, ge=1)
    send_names_instead_of_ids: bool = True
    matching_charts: NonEmptyString = '*'


ExporterType: TypeAlias = Annotated[GraphiteExporter, Field(discriminator='exporter_type')]


# Reporting Exporter Service

class ReportingExporterEntry(BaseModel):
    id: int
    enabled: bool
    attributes: ExporterType = Field(description='Specific attributes for the exporter')
    name: str = Field(description='User defined name of exporter configuration')


@single_argument_args('reporting_exporter_create')
class ReportingExporterCreateArgs(ReportingExporterEntry):
    id: Excluded = excluded_field()


class ReportingExporterCreateResult(BaseModel):
    result: ReportingExporterEntry


class ReportingExporterUpdate(ReportingExporterEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class ReportingExporterUpdateArgs(BaseModel):
    id: int
    reporting_exporter_update: ReportingExporterUpdate


class ReportingExporterUpdateResult(BaseModel):
    result: ReportingExporterEntry


class ReportingExporterDeleteArgs(BaseModel):
    id: int


class ReportingExporterDeleteResult(BaseModel):
    result: bool


class ReportingExporterSchemasArgs(BaseModel):
    pass


class ReportingExporterAttributeSchema(BaseModel):
    _name_: str
    title: str
    _required_: bool

    model_config = ConfigDict(extra='allow')


class ReportingExporterSchema(BaseModel):
    key: str
    schema_: list[ReportingExporterAttributeSchema] = Field(alias='schema')


class ReportingExporterSchemasResult(BaseModel):
    result: list[ReportingExporterSchema]
