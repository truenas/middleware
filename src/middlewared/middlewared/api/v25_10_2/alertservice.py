from middlewared.api.base import BaseModel, NonEmptyString
from .alert import AlertLevel
from .alertservice_attributes import AlertServiceAttributes


__all__ = [
    'AlertServiceEntry', 'AlertServiceCreateArgs', 'AlertServiceUpdateArgs', 'AlertServiceDeleteArgs',
    'AlertServiceTestArgs', 'AlertServiceCreateResult', 'AlertServiceUpdateResult', 'AlertServiceDeleteResult',
    'AlertServiceTestResult',
]


class AlertServiceCreate(BaseModel):
    name: NonEmptyString
    """Human-readable name for the alert service."""
    attributes: AlertServiceAttributes
    """Service-specific configuration attributes (credentials, endpoints, etc.)."""
    level: AlertLevel
    """Minimum alert severity level that triggers notifications through this service."""
    enabled: bool = True
    """Whether the alert service is active and will send notifications."""


class AlertServiceEntry(AlertServiceCreate):
    id: int
    """Unique identifier for the alert service."""
    type__title: str
    """Human-readable title for the alert service type."""


class AlertServiceCreateArgs(BaseModel):
    alert_service_create: AlertServiceCreate
    """Alert service configuration data for the new service."""


class AlertServiceUpdateArgs(BaseModel):
    id: int
    """ID of the alert service to update."""
    alert_service_update: AlertServiceCreate
    """Updated alert service configuration data."""


class AlertServiceDeleteArgs(BaseModel):
    id: int
    """ID of the alert service to delete."""


class AlertServiceTestArgs(BaseModel):
    alert_service_create: AlertServiceCreate
    """Alert service configuration to test for connectivity and functionality."""


class AlertServiceCreateResult(BaseModel):
    result: AlertServiceEntry
    """The created alert service configuration."""


class AlertServiceUpdateResult(BaseModel):
    result: AlertServiceEntry
    """The updated alert service configuration."""


class AlertServiceDeleteResult(BaseModel):
    result: bool
    """Returns `true` when the alert service is successfully deleted."""


class AlertServiceTestResult(BaseModel):
    result: bool
    """Returns `true` if the alert service test was successful."""
