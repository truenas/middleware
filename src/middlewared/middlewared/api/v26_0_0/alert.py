from datetime import datetime
from typing import Any, Literal, TypeAlias

from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, LongString, NotRequired, excluded_field

__all__ = [
    'AlertDismissArgs', 'AlertListArgs', 'AlertDismissResult', 'AlertListResult', 'AlertListCategoriesArgs',
    'AlertListCategoriesResult', 'AlertListPoliciesArgs', 'AlertListPoliciesResult', 'AlertRestoreArgs',
    'AlertRestoreResult', 'AlertClassesEntry', 'AlertClassesUpdateArgs', 'AlertClassesUpdateResult', 'Alert',
    'AlertListAddedEvent', 'AlertListChangedEvent', 'AlertListRemovedEvent', 'AlertLevel',
]

AlertLevel: TypeAlias = Literal['INFO', 'NOTICE', 'WARNING', 'ERROR', 'CRITICAL', 'ALERT', 'EMERGENCY']


class Alert(BaseModel):
    id: str = Field(description="Alert identifier used for API operations.")
    uuid: str = Field(description="Unique identifier for the alert.")
    source: str = Field(description="Source component that generated the alert.")
    klass: str = Field(description="Alert class identifier for categorization.")
    args: Any = Field(description="Arguments and parameters specific to the alert type.")
    node: str = Field(description="Node identifier in HA systems or hostname for single-node systems.")
    key: LongString = Field(description="Unique key used for alert deduplication and identification.")
    datetime_: datetime = Field(alias='datetime', description="Timestamp when the alert was first created.")
    last_occurrence: datetime = Field(description="Timestamp of the most recent occurrence of this alert.")
    dismissed: bool = Field(description="Whether the alert has been manually dismissed by a user.")
    mail: Any = Field(description="Email notification configuration and status for this alert.")
    text: LongString = Field(description="Human-readable description of the alert.")
    level: str = Field(description="Severity level of the alert (INFO, WARNING, ERROR, etc.).")
    formatted: LongString | None = Field(description="Formatted alert message with HTML.")
    one_shot: bool = Field(description="Whether this alert will not be dismissed automatically.")


class AlertCategoryClass(BaseModel):
    id: str = Field(description="Unique identifier for the alert class.")
    title: str = Field(description="Human-readable title for the alert class.")
    level: str = Field(description="Default severity level for alerts in this class.")
    product_types: list[Literal["COMMUNITY_EDITION", "ENTERPRISE"]] = Field(
        description="Product types where this alert class is available.",
    )
    proactive_support: bool = Field(description="Whether this alert class is included in proactive support monitoring.")


class AlertCategory(BaseModel):
    id: str = Field(description="Unique identifier for the alert category.")
    title: str = Field(description="Human-readable title for the alert category.")
    classes: list[AlertCategoryClass] = Field(description="Array of alert classes within this category.")


class AlertClassConfiguration(BaseModel):
    level: AlertLevel = Field(default=NotRequired, description="Severity level for alerts of this class.")
    policy: Literal['IMMEDIATELY', 'HOURLY', 'DAILY', 'NEVER'] = Field(
        default=NotRequired,
        description=(
            "Notification policy for alerts of this class.\n"
            "\n"
            "* `IMMEDIATELY`: Send notifications as soon as alerts occur\n"
            "* `HOURLY`: Batch notifications and send hourly\n"
            "* `DAILY`: Batch notifications and send daily\n"
            "* `NEVER`: Do not send notifications for this alert class"
        ),
    )
    proactive_support: bool = Field(
        default=NotRequired,
        description="Whether to include alerts of this class in proactive support reporting.",
    )


class AlertClassesEntry(BaseModel):
    id: int = Field(description="Unique identifier for the alert classes configuration.")
    classes: dict[str, AlertClassConfiguration] = Field(
        description="Object mapping alert class names to their configuration settings.",
    )


class AlertClassesUpdate(AlertClassesEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class AlertDismissArgs(BaseModel):
    uuid: str = Field(description="UUID of the alert to dismiss.")


class AlertDismissResult(BaseModel):
    result: None = Field(description="Returns `null` when the alert is successfully dismissed.")


class AlertListArgs(BaseModel):
    pass


class AlertListResult(BaseModel):
    result: list[Alert] = Field(description="Array of all current alerts in the system.")


class AlertListCategoriesOptions(BaseModel):
    include_all_products: bool = Field(
        default=False,
        description="Include alert classes for all products, not just the current one.",
    )
    include_hidden_classes: bool = Field(default=False, description="Include hidden alert classes.")


class AlertListCategoriesArgs(BaseModel):
    options: AlertListCategoriesOptions = Field(default=AlertListCategoriesOptions(), description="List options.")


class AlertListCategoriesResult(BaseModel):
    result: list[AlertCategory] = Field(description="Array of available alert categories and their classes.")


class AlertListPoliciesArgs(BaseModel):
    pass


class AlertListPoliciesResult(BaseModel):
    result: list[str] = Field(description="Array of available notification policies for alert classes.")


class AlertRestoreArgs(BaseModel):
    uuid: str = Field(description="UUID of the dismissed alert to restore.")


class AlertRestoreResult(BaseModel):
    result: None = Field(description="Returns `null` when the alert is successfully restored.")


class AlertClassesUpdateArgs(BaseModel):
    alert_class_update: AlertClassesUpdate = Field(description="Updated alert class configuration settings.")


class AlertClassesUpdateResult(BaseModel):
    result: AlertClassesEntry = Field(description="The updated alert classes configuration.")


class AlertListAddedEvent(BaseModel):
    id: int = Field(description="Event identifier for the added alert.")
    fields: Alert = Field(description="Complete alert data for the newly added alert.")


class AlertListChangedEvent(BaseModel):
    id: int = Field(description="Event identifier for the changed alert.")
    fields: Alert = Field(description="Updated alert data with changes.")


class AlertListRemovedEvent(BaseModel):
    id: int = Field(description="Event identifier for the removed alert.")
