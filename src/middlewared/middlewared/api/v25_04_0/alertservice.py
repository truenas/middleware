from middlewared.api.base import BaseModel, NonEmptyString


__all__ = [
    'AlertServiceEntry', 'AlertServiceCreateArgs', 'AlertServiceUpdateArgs', 'AlertServiceDeleteArgs',
    'AlertServiceTestArgs', 'AlertServiceCreateResult', 'AlertServiceUpdateResult', 'AlertServiceDeleteResult',
    'AlertServiceTestResult',
]


class AlertServiceCreate(BaseModel):
    name: NonEmptyString
    type: str
    attributes: dict
    level: str
    enabled: bool = True


class AlertServiceEntry(AlertServiceCreate):
    id: int
    type__title: str


###########   Arguments   ###########


class AlertServiceCreateArgs(BaseModel):
    alert_service_create: AlertServiceCreate


class AlertServiceUpdateArgs(BaseModel):
    id: int
    alert_service_update: AlertServiceCreate


class AlertServiceDeleteArgs(BaseModel):
    id: int


class AlertServiceTestArgs(BaseModel):
    alert_service_create: AlertServiceCreate


###########   Returns   ###########


class AlertServiceCreateResult(BaseModel):
    result: AlertServiceEntry


class AlertServiceUpdateResult(BaseModel):
    result: AlertServiceEntry


class AlertServiceDeleteResult(BaseModel):
    result: bool


class AlertServiceTestResult(BaseModel):
    result: bool
