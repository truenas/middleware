from typing import Annotated, Literal, TypeAlias

from pydantic import ConfigDict, Field

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args
)


__all__ = [
    'ReportingExporterEntry', 'ReportingExportsCreateArgs', 'ReportingExportsCreateResult', 'GraphiteExporter',
    'ReportingExportsUpdateArgs', 'ReportingExportsUpdateResult', 'ReportingExportsDeleteArgs',
    'ReportingExportsDeleteResult', 'ReportingExportsExporterSchemasArgs', 'ReportingExportsExporterSchemasResult',
]


# Exporter models

class GraphiteExporter(BaseModel):
    exporter_type: Literal['GRAPHITE']
    """Type of exporter - Graphite."""
    destination_ip: NonEmptyString
    """IP address of the Graphite server."""
    destination_port: int = Field(ge=1, le=65535)
    """Port number of the Graphite server."""
    prefix: str = 'scale'
    """Prefix to prepend to all metric names."""
    namespace: NonEmptyString
    """Namespace to organize metrics under."""
    update_every: int = Field(default=1, ge=1)
    """Interval in seconds between metric updates."""
    buffer_on_failures: int = Field(default=10, ge=1)
    """Number of updates to buffer when Graphite server is unavailable."""
    send_names_instead_of_ids: bool = True
    """Whether to send human-readable names instead of internal IDs."""
    matching_charts: NonEmptyString = '*'
    """Pattern to match charts for export (supports wildcards)."""


ExporterType: TypeAlias = Annotated[GraphiteExporter, Field(discriminator='exporter_type')]


# Reporting Exporter Service

class ReportingExporterEntry(BaseModel):
    id: int
    """Unique identifier for the reporting exporter."""
    enabled: bool
    """Whether this exporter is enabled and active."""
    attributes: ExporterType
    """Specific attributes for the exporter."""
    name: str
    """User defined name of exporter configuration."""


@single_argument_args('reporting_exporter_create')
class ReportingExportsCreateArgs(ReportingExporterEntry):
    id: Excluded = excluded_field()


class ReportingExportsCreateResult(BaseModel):
    result: ReportingExporterEntry
    """The newly created reporting exporter configuration."""


class ReportingExporterUpdate(ReportingExporterEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class ReportingExportsUpdateArgs(BaseModel):
    id: int
    """ID of the reporting exporter to update."""
    reporting_exporter_update: ReportingExporterUpdate
    """Updated configuration for the reporting exporter."""


class ReportingExportsUpdateResult(BaseModel):
    result: ReportingExporterEntry
    """The updated reporting exporter configuration."""


class ReportingExportsDeleteArgs(BaseModel):
    id: int
    """ID of the reporting exporter to delete."""


class ReportingExportsDeleteResult(BaseModel):
    result: bool
    """Whether the reporting exporter was successfully deleted."""


class ReportingExportsExporterSchemasArgs(BaseModel):
    pass


class ReportingExporterAttributeSchema(BaseModel):
    name: str = Field(alias='_name_')
    """Internal name of the exporter attribute."""
    title: str
    """Human-readable title for the attribute."""
    required: bool = Field(alias='_required_')
    """Whether this attribute is required for the exporter configuration."""

    model_config = ConfigDict(extra='allow')


class ReportingExporterSchema(BaseModel):
    key: str
    """Unique key identifying the exporter type."""
    schema_: list[ReportingExporterAttributeSchema] = Field(alias='schema')
    """Array of attribute definitions for this exporter type."""


class ReportingExportsExporterSchemasResult(BaseModel):
    result: list[ReportingExporterSchema]
    """Array of available exporter schema definitions."""
