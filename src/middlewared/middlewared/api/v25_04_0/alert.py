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


###########   Arguments   ###########


class AlertDismissArgs(BaseModel):
    uuid: str


class AlertListArgs(BaseModel):
    pass


class AlertListCategoriesArgs(BaseModel):
    pass


class AlertListPoliciesArgs(BaseModel):
    pass


class AlertRestoreArgs(BaseModel):
    uuid: str


class AlertOneshotCreateArgs(BaseModel):
    klass: str
    args: Any


class AlertOneshotDeleteArgs(BaseModel):
    klass: str | list[str]
    query: Any = None


class AlertClassesUpdateArgs(BaseModel):
    alertclasses_update: AlertClassesUpdate = Field(default=AlertClassesUpdate())


###########   Returns   ###########


class AlertDismissResult(BaseModel):
    result: None


class AlertListResult(BaseModel):
    result: list[Alert]


class AlertListCategoriesResult(BaseModel):
    result: list[AlertCategory]


class AlertListPoliciesResult(BaseModel):
    result: list[str]


class AlertRestoreResult(BaseModel):
    result: None


class AlertOneshotCreateResult(BaseModel):
    result: None


class AlertOneshotDeleteResult(BaseModel):
    result: None


class AlertClassesUpdateResult(BaseModel):
    result: AlertClassesEntry
