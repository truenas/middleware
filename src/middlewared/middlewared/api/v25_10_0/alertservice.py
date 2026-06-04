from pydantic import Field

from middlewared.api.base import BaseModel, NonEmptyString

from .alert import AlertLevel
from .alertservice_attributes import AlertServiceAttributes

__all__ = [
    'AlertServiceEntry', 'AlertServiceCreateArgs', 'AlertServiceUpdateArgs', 'AlertServiceDeleteArgs',
    'AlertServiceTestArgs', 'AlertServiceCreateResult', 'AlertServiceUpdateResult', 'AlertServiceDeleteResult',
    'AlertServiceTestResult',
]


class AlertServiceCreate(BaseModel):
    name: NonEmptyString = Field(description="Human-readable name for the alert service.")
    attributes: AlertServiceAttributes = Field(
        description="Service-specific configuration attributes (credentials, endpoints, etc.).",
    )
    level: AlertLevel = Field(
        description="Minimum alert severity level that triggers notifications through this service.",
    )
    enabled: bool = Field(default=True, description="Whether the alert service is active and will send notifications.")

    @classmethod
    def from_previous(cls, value):
        value["attributes"]["type"] = value.pop("type")
        return value

    @classmethod
    def to_previous(cls, value):
        value["type"] = value["attributes"].pop("type")
        return value


class AlertServiceEntry(AlertServiceCreate):
    id: int = Field(description="Unique identifier for the alert service.")
    type__title: str = Field(description="Human-readable title for the alert service type.")


class AlertServiceCreateArgs(BaseModel):
    alert_service_create: AlertServiceCreate = Field(
        description="Alert service configuration data for the new service.",
    )


class AlertServiceUpdateArgs(BaseModel):
    id: int = Field(description="ID of the alert service to update.")
    alert_service_update: AlertServiceCreate = Field(description="Updated alert service configuration data.")


class AlertServiceDeleteArgs(BaseModel):
    id: int = Field(description="ID of the alert service to delete.")


class AlertServiceTestArgs(BaseModel):
    alert_service_create: AlertServiceCreate = Field(
        description="Alert service configuration to test for connectivity and functionality.",
    )


class AlertServiceCreateResult(BaseModel):
    result: AlertServiceEntry = Field(description="The created alert service configuration.")


class AlertServiceUpdateResult(BaseModel):
    result: AlertServiceEntry = Field(description="The updated alert service configuration.")


class AlertServiceDeleteResult(BaseModel):
    result: bool = Field(description="Returns `true` when the alert service is successfully deleted.")


class AlertServiceTestResult(BaseModel):
    result: bool = Field(description="Returns `true` if the alert service test was successful.")
