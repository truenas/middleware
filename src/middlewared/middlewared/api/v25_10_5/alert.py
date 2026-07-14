from datetime import datetime
from typing import Any, Literal, TypeAlias

from pydantic import Field

from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LongString, NotRequired


__all__ = [
    'AlertDismissArgs', 'AlertListArgs', 'AlertDismissResult', 'AlertListResult', 'AlertListCategoriesArgs',
    'AlertListCategoriesResult', 'AlertListPoliciesArgs', 'AlertListPoliciesResult', 'AlertRestoreArgs',
    'AlertRestoreResult', 'AlertClassesEntry', 'AlertClassesUpdateArgs', 'AlertClassesUpdateResult', 'Alert',
    'AlertListAddedEvent', 'AlertListChangedEvent', 'AlertListRemovedEvent', 'AlertLevel',
]

AlertLevel: TypeAlias = Literal['INFO', 'NOTICE', 'WARNING', 'ERROR', 'CRITICAL', 'ALERT', 'EMERGENCY']


class Alert(BaseModel):
    uuid: str
    """Unique identifier for the alert."""
    source: str
    """Source component that generated the alert."""
    klass: str
    """Alert class identifier for categorization."""
    args: Any
    """Arguments and parameters specific to the alert type."""
    node: str
    """Node identifier in HA systems or hostname for single-node systems."""
    key: LongString
    """Unique key used for alert deduplication and identification."""
    datetime_: datetime = Field(alias='datetime')
    """Timestamp when the alert was first created."""
    last_occurrence: datetime
    """Timestamp of the most recent occurrence of this alert."""
    dismissed: bool
    """Whether the alert has been manually dismissed by a user."""
    mail: Any
    """Email notification configuration and status for this alert."""
    text: LongString
    """Human-readable description of the alert."""
    id: str
    """Alert identifier used for API operations."""
    level: str
    """Severity level of the alert (INFO, WARNING, ERROR, etc.)."""
    formatted: LongString | None
    """Formatted alert message with HTML."""
    one_shot: bool
    """Whether this alert will not be dismissed automatically."""


class AlertCategoryClass(BaseModel):
    id: str
    """Unique identifier for the alert class."""
    title: str
    """Human-readable title for the alert class."""
    level: str
    """Default severity level for alerts in this class."""
    proactive_support: bool
    """Whether this alert class is included in proactive support monitoring."""


class AlertCategory(BaseModel):
    id: str
    """Unique identifier for the alert category."""
    title: str
    """Human-readable title for the alert category."""
    classes: list[AlertCategoryClass]
    """Array of alert classes within this category."""


class AlertClassConfiguration(BaseModel):
    level: AlertLevel = NotRequired
    """Severity level for alerts of this class."""
    policy: Literal['IMMEDIATELY', 'HOURLY', 'DAILY', 'NEVER'] = NotRequired
    """Notification policy for alerts of this class.

    * `IMMEDIATELY`: Send notifications as soon as alerts occur
    * `HOURLY`: Batch notifications and send hourly
    * `DAILY`: Batch notifications and send daily
    * `NEVER`: Do not send notifications for this alert class
    """
    proactive_support: bool = NotRequired
    """Whether to include alerts of this class in proactive support reporting."""


class AlertClassesEntry(BaseModel):
    id: int
    """Unique identifier for the alert classes configuration."""
    classes: dict[str, AlertClassConfiguration]
    """Object mapping alert class names to their configuration settings."""


class AlertClassesUpdate(AlertClassesEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class AlertDismissArgs(BaseModel):
    uuid: str
    """UUID of the alert to dismiss."""


class AlertDismissResult(BaseModel):
    result: None
    """Returns `null` when the alert is successfully dismissed."""


class AlertListArgs(BaseModel):
    pass


class AlertListResult(BaseModel):
    result: list[Alert]
    """Array of all current alerts in the system."""


class AlertListCategoriesArgs(BaseModel):
    pass


class AlertListCategoriesResult(BaseModel):
    result: list[AlertCategory]
    """Array of available alert categories and their classes."""


class AlertListPoliciesArgs(BaseModel):
    pass


class AlertListPoliciesResult(BaseModel):
    result: list[str]
    """Array of available notification policies for alert classes."""


class AlertRestoreArgs(BaseModel):
    uuid: str
    """UUID of the dismissed alert to restore."""


class AlertRestoreResult(BaseModel):
    result: None
    """Returns `null` when the alert is successfully restored."""


class AlertClassesUpdateArgs(BaseModel):
    alert_class_update: AlertClassesUpdate
    """Updated alert class configuration settings."""


class AlertClassesUpdateResult(BaseModel):
    result: AlertClassesEntry
    """The updated alert classes configuration."""


class AlertListAddedEvent(BaseModel):
    id: int
    """Event identifier for the added alert."""
    fields: Alert
    """Complete alert data for the newly added alert."""


class AlertListChangedEvent(BaseModel):
    id: int
    """Event identifier for the changed alert."""
    fields: Alert
    """Updated alert data with changes."""


class AlertListRemovedEvent(BaseModel):
    id: int
    """Event identifier for the removed alert."""
