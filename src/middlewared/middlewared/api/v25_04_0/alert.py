from datetime import datetime
from typing import Any

from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongString


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
    datetime_: datetime = Field(..., alias='datetime')
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


class AlertClassesEntry(BaseModel):
    id: int
    classes: dict


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
    data: AlertClassesUpdate


class AlertClassesUpdateResult(BaseModel):
    result: AlertClassesEntry
