from typing import Any

from pydantic import Field

from middlewared.api.base import BaseModel, LongString


__all__ = [
    'AlertDismissArgs', 'AlertListArgs', 'AlertDismissResult', 'AlertListResult', 'AlertListCategoriesArgs',
    'AlertListCategoriesResult', 'AlertListPoliciesArgs', 'AlertListPoliciesResult', 'AlertRestoreArgs',
    'AlertRestoreResult', 'AlertOneshotCreateArgs', 'AlertOneshotCreateResult', 'AlertOneshotDeleteArgs',
    'AlertOneshotDeleteResult', 'AlertClassesEntry', 'AlertClassesUpdateArgs', 'AlertClassesUpdateResult', 'Alert',
]


class Alert(BaseModel):
    uuid: str
    source: str
    klass: str
    args: Any
    node: str
    key: LongString
    datetime: str
    last_occurrence: str
    dismissed: bool
    mail: Any
    text: LongString
    id: str
    level: str
    formatted: LongString | None
    one_shot: bool


class AlertCategoryClass(BaseModel):
    id: str
    title: str
    level: str
    proactive_support: bool


class AlertCategory(BaseModel):
    id: str
    title: str
    classes: list[AlertCategoryClass]


class AlertClassesUpdate(BaseModel):
    classes: dict = {}


class AlertClassesEntry(AlertClassesUpdate):
    id: int


class AlertDismissArgs(BaseModel):
    uuid: str


class AlertDismissResult(BaseModel):
    result: None


class AlertListArgs(BaseModel):
    pass


class AlertListResult(BaseModel):
    result: list[Alert]


class AlertListCategoriesArgs(BaseModel):
    pass


class AlertListCategoriesResult(BaseModel):
    result: list[AlertCategory]



class AlertListPoliciesArgs(BaseModel):
    pass


class AlertListPoliciesResult(BaseModel):
    result: list[str]


class AlertOneshotCreateArgs(BaseModel):
    klass: str
    args: Any


class AlertOneshotCreateResult(BaseModel):
    result: None


class AlertOneshotDeleteArgs(BaseModel):
    klass: str | list[str]
    query: Any = None


class AlertOneshotDeleteResult(BaseModel):
    result: None


class AlertRestoreArgs(BaseModel):
    uuid: str


class AlertRestoreResult(BaseModel):
    result: None


class AlertClassesUpdateArgs(BaseModel):
    alertclasses_update: AlertClassesUpdate = Field(default=AlertClassesUpdate())


class AlertClassesUpdateResult(BaseModel):
    result: AlertClassesEntry


class DiskTemperatureAlertsArgs(BaseModel):
    names: list[str]


class DiskTemperatureAlertsResult(BaseModel):
    result: list[Alert]
