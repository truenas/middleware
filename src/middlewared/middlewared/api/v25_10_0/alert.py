from datetime import datetime
from typing import Any, Literal, TypeAlias

from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongString


__all__ = [
    'AlertDismissArgs', 'AlertListArgs', 'AlertDismissResult', 'AlertListResult', 'AlertListCategoriesArgs',
    'AlertListCategoriesResult', 'AlertListPoliciesArgs', 'AlertListPoliciesResult', 'AlertRestoreArgs',
    'AlertRestoreResult', 'AlertClassesEntry', 'AlertClassesUpdateArgs', 'AlertClassesUpdateResult', 'Alert',
    'AlertListAddedEvent', 'AlertListChangedEvent', 'AlertListRemovedEvent', 'AlertLevel',
]

AlertLevel: TypeAlias = Literal['INFO', 'NOTICE', 'WARNING', 'ERROR', 'CRITICAL', 'ALERT', 'EMERGENCY']


class Alert(BaseModel):
    uuid: str
    source: str
    klass: str
    args: Any
    node: str
    key: LongString
    datetime_: datetime = Field(alias='datetime')
    last_occurrence: datetime
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


class AlertClassConfiguration(BaseModel):
    level: AlertLevel
    policy: Literal['IMMEDIATELY', 'HOURLY', 'DAILY', 'NEVER']
    proactive_support: bool = False


class AlertClassesEntry(BaseModel):
    id: int
    classes: dict[str, AlertClassConfiguration]


class AlertClassesUpdate(AlertClassesEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


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


class AlertRestoreArgs(BaseModel):
    uuid: str


class AlertRestoreResult(BaseModel):
    result: None


class AlertClassesUpdateArgs(BaseModel):
    alert_class_update: AlertClassesUpdate


class AlertClassesUpdateResult(BaseModel):
    result: AlertClassesEntry


class AlertListAddedEvent(BaseModel):
    id: int
    fields: Alert


class AlertListChangedEvent(BaseModel):
    id: int
    fields: Alert


class AlertListRemovedEvent(BaseModel):
    id: int
