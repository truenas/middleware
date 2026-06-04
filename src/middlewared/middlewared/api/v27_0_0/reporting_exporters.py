from typing import Annotated, Literal, TypeAlias

from pydantic import ConfigDict, Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    ForUpdateMetaclass,
    NonEmptyString,
    excluded_field,
    single_argument_args,
)

__all__ = [
    'ReportingExportsEntry', 'ReportingExportsCreateArgs', 'ReportingExportsCreateResult', 'GraphiteExporter',
    'ReportingExportsUpdateArgs', 'ReportingExportsUpdateResult', 'ReportingExportsDeleteArgs',
    'ReportingExportsDeleteResult', 'ReportingExportsExporterSchemasArgs', 'ReportingExportsExporterSchemasResult',
]


# Exporter models

class GraphiteExporter(BaseModel):
    exporter_type: Literal['GRAPHITE'] = Field(description="Type of exporter - Graphite.")
    destination_ip: NonEmptyString = Field(description="IP address of the Graphite server.")
    destination_port: int = Field(ge=1, le=65535, description="Port number of the Graphite server.")
    prefix: str = Field(default='scale', description="Prefix to prepend to all metric names.")
    namespace: NonEmptyString = Field(description="Namespace to organize metrics under.")
    update_every: int = Field(default=1, ge=1, description="Interval in seconds between metric updates.")
    buffer_on_failures: int = Field(
        default=10,
        ge=1,
        description="Number of updates to buffer when Graphite server is unavailable.",
    )
    send_names_instead_of_ids: bool = Field(
        default=True,
        description="Whether to send human-readable names instead of internal IDs.",
    )
    matching_charts: NonEmptyString = Field(
        default='*',
        description="Pattern to match charts for export (supports wildcards).",
    )


ExporterType: TypeAlias = Annotated[GraphiteExporter, Field(discriminator='exporter_type')]


# Reporting Exporter Service

class ReportingExportsEntry(BaseModel):
    id: int = Field(description="Unique identifier for the reporting exporter.")
    enabled: bool = Field(description="Whether this exporter is enabled and active.")
    attributes: ExporterType = Field(description="Specific attributes for the exporter.")
    name: str = Field(description="User defined name of exporter configuration.")


@single_argument_args('reporting_exporter_create')
class ReportingExportsCreateArgs(ReportingExportsEntry):
    id: Excluded = excluded_field()


class ReportingExportsCreateResult(BaseModel):
    result: ReportingExportsEntry = Field(description="The newly created reporting exporter configuration.")


class ReportingExporterUpdate(ReportingExportsEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class ReportingExportsUpdateArgs(BaseModel):
    id: int = Field(description="ID of the reporting exporter to update.")
    reporting_exporter_update: ReportingExporterUpdate = Field(
        description="Updated configuration for the reporting exporter.",
    )


class ReportingExportsUpdateResult(BaseModel):
    result: ReportingExportsEntry = Field(description="The updated reporting exporter configuration.")


class ReportingExportsDeleteArgs(BaseModel):
    id: int = Field(description="ID of the reporting exporter to delete.")


class ReportingExportsDeleteResult(BaseModel):
    result: bool = Field(description="Whether the reporting exporter was successfully deleted.")


class ReportingExportsExporterSchemasArgs(BaseModel):
    pass


class ReportingExporterAttributeSchema(BaseModel):
    name: str = Field(alias='_name_', description="Internal name of the exporter attribute.")
    title: str = Field(description="Human-readable title for the attribute.")
    required: bool = Field(
        alias='_required_',
        description="Whether this attribute is required for the exporter configuration.",
    )

    model_config = ConfigDict(extra='allow')


class ReportingExporterSchema(BaseModel):
    key: str = Field(description="Unique key identifying the exporter type.")
    schema_: list[ReportingExporterAttributeSchema] = Field(
        alias='schema',
        description="Array of attribute definitions for this exporter type.",
    )


class ReportingExportsExporterSchemasResult(BaseModel):
    result: list[ReportingExporterSchema] = Field(description="Array of available exporter schema definitions.")
