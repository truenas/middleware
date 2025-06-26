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
    attributes: AlertServiceAttributes
    level: AlertLevel
    enabled: bool = True

    @classmethod
    def from_previous(cls, value):
        value["attributes"]["type"] = value.pop("type")
        return value

    @classmethod
    def to_previous(cls, value):
        value["type"] = value["attributes"].pop("type")
        return value


class AlertServiceEntry(AlertServiceCreate):
    id: int
    type__title: str


class AlertServiceCreateArgs(BaseModel):
    alert_service_create: AlertServiceCreate


class AlertServiceUpdateArgs(BaseModel):
    id: int
    alert_service_update: AlertServiceCreate


class AlertServiceDeleteArgs(BaseModel):
    id: int


class AlertServiceTestArgs(BaseModel):
    alert_service_create: AlertServiceCreate


class AlertServiceCreateResult(BaseModel):
    result: AlertServiceEntry


class AlertServiceUpdateResult(BaseModel):
    result: AlertServiceEntry


class AlertServiceDeleteResult(BaseModel):
    result: bool


class AlertServiceTestResult(BaseModel):
    result: bool
