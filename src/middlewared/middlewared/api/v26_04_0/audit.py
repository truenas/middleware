from datetime import datetime
from typing import Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel, single_argument_args, ForUpdateMetaclass, Excluded, excluded_field, query_result
)
from .common import QueryFilters, QueryOptions


__all__ = [
    "AuditEntry", "AuditDownloadReportArgs", "AuditDownloadReportResult", "AuditQueryArgs", "AuditQueryResult",
    "AuditExportArgs", "AuditExportResult", "AuditUpdateArgs", "AuditUpdateResult",
]


# In theory, this should be a type to represent the values able to be passed to `uuid.UUID()`.
# Unfortunately, some values we store would fail this validation.
UUID = str | int


class AuditEntrySpace(BaseModel):
    used: int
    """Total space used by the audit dataset in bytes."""
    used_by_dataset: int
    """Space used by the dataset itself (not including snapshots or reservations) in bytes."""
    used_by_reservation: int
    """Space reserved for the dataset in bytes."""
    used_by_snapshots: int
    """Space used by snapshots of the audit dataset in bytes."""
    available: int
    """Available space remaining for the audit dataset in bytes."""


class AuditEntryEnabledServices(BaseModel):
    MIDDLEWARE: list
    """Array of middleware audit event types that are enabled."""
    SMB: list
    """Array of SMB share names or audit event types that are enabled."""
    SUDO: list[str]
    """Array of sudo commands or users that are being audited."""


class AuditEntry(BaseModel):
    id: int
    """Unique identifier for the audit configuration."""
    retention: int = Field(ge=1, le=30)
    """Number of days to retain local audit messages."""
    reservation: int = Field(ge=0, le=100)
    """Size in GiB of refreservation to set on ZFS dataset where the audit databases are stored. The refreservation \
    specifies the minimum amount of space guaranteed to the dataset, and counts against the space available for other \
    datasets in the zpool where the audit dataset is located."""
    quota: int = Field(ge=0, le=100)
    """Size in GiB of the maximum amount of space that may be consumed by the dataset where the audit dabases are \
    stored."""
    quota_fill_warning: int = Field(ge=5, le=80)
    """Percentage used of dataset quota at which to generate a warning alert."""
    quota_fill_critical: int = Field(ge=50, le=95)
    """Percentage used of dataset quota at which to generate a critical alert."""
    remote_logging_enabled: bool
    """Logging to a remote syslog server is enabled on TrueNAS, and audit logs are \
    included in what is sent remotely."""
    space: AuditEntrySpace
    """ZFS dataset properties relating space used and available for the dataset where the audit databases are \
    written."""
    enabled_services: AuditEntryEnabledServices
    """JSON object with key denoting service, and value containing a JSON array of what aspects of this service are \
    being audited. In the case of the SMB audit, the list contains share names of shares for which auditing is \
    enabled."""


class AuditQuery(BaseModel):
    services: list[Literal['MIDDLEWARE', 'SMB', 'SUDO', 'SYSTEM']] = ['MIDDLEWARE', 'SUDO']
    """Array of services to include in the audit query."""
    query_filters: QueryFilters = Field(alias='query-filters', default=[])
    """Array of filters to apply to the audit query results."""
    query_options: QueryOptions = Field(alias='query-options', default=QueryOptions())
    """If the query-option `force_sql_filters` is true, then the query will be converted into a more efficient form \
    for better performance. This will not be possible if filters use keys within `svc_data` and `event_data`."""
    remote_controller: bool = False
    """HA systems may direct the query to the 'remote' controller by including 'remote_controller=True'. The default \
    is the 'current' controller."""


class AuditExportQueryOptions(QueryOptions):
    extra: Excluded = excluded_field()
    count: Excluded = excluded_field()
    get: Excluded = excluded_field()


class AuditExport(AuditQuery):
    query_options: AuditExportQueryOptions = Field(alias='query-options', default=AuditExportQueryOptions())
    export_format: Literal['CSV', 'JSON', 'YAML'] = 'JSON'
    """Format for exporting audit data."""


class AuditQueryResultItem(BaseModel):
    audit_id: UUID | None
    """GUID uniquely identifying this specific audit event."""
    message_timestamp: int
    """Unix timestamp for when the audit event was written to the auditing database."""
    timestamp: datetime
    """Converted ISO-8601 timestamp from application recording when event occurred."""
    address: str
    """IP address of client performing action that generated the audit message."""
    username: str
    """Username used by client performing action."""
    session: UUID | None
    """GUID uniquely identifying the client session."""
    service: Literal['MIDDLEWARE', 'SMB', 'SUDO', 'SYSTEM']
    """Name of the service that generated the message. This will be one of the names specified in `services`."""
    service_data: dict | None
    """JSON object containing variable data depending on the particular service. See TrueNAS auditing documentation \
    for the service in question."""
    event: str
    """Name of the event type that generated the audit record. Each service has its own unique event identifiers."""
    event_data: dict | None
    """JSON object containing variable data depending on the particular event type. See TrueNAS auditing documentation \
    for the service in question."""
    success: bool
    """The action generating the event message succeeded."""


class AuditUpdate(AuditEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    remote_logging_enabled: Excluded = excluded_field()
    space: Excluded = excluded_field()
    enabled_services: Excluded = excluded_field()


@single_argument_args('data')
class AuditDownloadReportArgs(BaseModel):
    report_name: str
    """Name of the audit report to download."""


class AuditDownloadReportResult(BaseModel):
    result: None
    """Returns `null` when the audit report download is initiated."""


class AuditExportArgs(BaseModel):
    data: AuditExport = AuditExport()
    """Audit export configuration specifying services, filters, and format."""


class AuditExportResult(BaseModel):
    result: str
    """Path to the exported audit data file."""


class AuditQueryArgs(BaseModel):
    data: AuditQuery = AuditQuery()
    """Audit query configuration specifying services, filters, and options."""


AuditQueryResult = query_result(AuditQueryResultItem, name="AuditQueryResult")


class AuditUpdateArgs(BaseModel):
    data: AuditUpdate
    """Updated audit configuration settings."""


class AuditUpdateResult(BaseModel):
    result: AuditEntry
    """The updated audit configuration."""
