from datetime import datetime
from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, single_argument_args, ForUpdateMetaclass, Excluded, excluded_field
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
    used_by_dataset: int
    used_by_reservation: int
    used_by_snapshots: int
    available: int


class AuditEntryEnabledServices(BaseModel):
    MIDDLEWARE: list
    SMB: list
    SUDO: list[str]


class AuditEntry(BaseModel):
    id: int
    retention: int = Field(ge=1, le=30)
    """Number of days to retain local audit messages."""
    reservation: int = Field(ge=0, le=100)
    """Size in GiB of refreservation to set on ZFS dataset where the audit databases are stored. The refreservation
    specifies the minimum amount of space guaranteed to the dataset, and counts against the space available for other
    datasets in the zpool where the audit dataset is located."""
    quota: int = Field(ge=0, le=100)
    """Size in GiB of the maximum amount of space that may be consumed by the dataset where the audit dabases are
    stored."""
    quota_fill_warning: int = Field(ge=5, le=80)
    """Percentage used of dataset quota at which to generate a warning alert."""
    quota_fill_critical: int = Field(ge=50, le=95)
    """Percentage used of dataset quota at which to generate a critical alert."""
    remote_logging_enabled: bool
    """Boolean indicating whether logging to a remote syslog server is enabled on TrueNAS and if audit logs are
    included in what is sent remotely."""
    space: AuditEntrySpace
    """ZFS dataset properties relating space used and available for the dataset where the audit databases are
    written."""
    enabled_services: AuditEntryEnabledServices
    """JSON object with key denoting service, and value containing a JSON array of what aspects of this service are
    being audited. In the case of the SMB audit, the list contains share names of shares for which auditing is
    enabled."""


class AuditQuery(BaseModel):
    services: list[Literal['MIDDLEWARE', 'SMB', 'SUDO', 'SYSTEM']] = ['MIDDLEWARE', 'SUDO']
    query_filters: QueryFilters = Field(alias='query-filters', default=[])
    query_options: QueryOptions = Field(alias='query-options', default_factory=QueryOptions)
    """If the query-option `force_sql_filters` is true, then the query will be converted into a more efficient form for
    better performance. This will not be possible if filters use keys within `svc_data` and `event_data`."""
    remote_controller: bool = False
    """HA systems may direct the query to the 'remote' controller by including 'remote_controller=True'. The default
    is the 'current' controller."""


class AuditExport(AuditQuery):
    export_format: Literal['CSV', 'JSON', 'YAML'] = 'JSON'


class AuditQueryResultItem(BaseModel, metaclass=ForUpdateMetaclass):
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
    """JSON object containing variable data depending on the particular service. See TrueNAS auditing documentation for
    the service in question."""
    event: str
    """Name of the event type that generated the audit record. Each service has its own unique event identifiers."""
    event_data: dict | None
    """JSON object containing variable data depending on the particular event type. See TrueNAS auditing documentation
    for the service in question."""
    success: bool
    """Boolean value indicating whether the action generating the event message succeeded."""


class AuditUpdate(AuditEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    remote_logging_enabled: Excluded = excluded_field()
    space: Excluded = excluded_field()
    enabled_services: Excluded = excluded_field()


@single_argument_args('data')
class AuditDownloadReportArgs(BaseModel):
    report_name: str


class AuditDownloadReportResult(BaseModel):
    result: None


class AuditExportArgs(BaseModel):
    data: AuditExport = Field(default_factory=AuditExport)


class AuditExportResult(BaseModel):
    result: str


class AuditQueryArgs(BaseModel):
    data: AuditQuery = Field(default_factory=AuditQuery)


class AuditQueryResult(BaseModel):
    result: int | AuditQueryResultItem | list[AuditQueryResultItem]


class AuditUpdateArgs(BaseModel):
    data: AuditUpdate


class AuditUpdateResult(BaseModel):
    result: AuditEntry
