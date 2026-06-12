from __future__ import annotations

from dataclasses import dataclass
import textwrap

from middlewared.alert.base import (
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    OneShotAlertClass,
)
import middlewared.sqlalchemy as sa


class AlertModel(sa.Model):
    __tablename__ = "system_alert"

    id = sa.Column(sa.Integer(), primary_key=True)
    node = sa.Column(sa.String(100))
    source = sa.Column(sa.Text())
    key = sa.Column(sa.Text())
    datetime = sa.Column(sa.DateTime())
    last_occurrence = sa.Column(sa.DateTime())
    text = sa.Column(sa.Text())
    args = sa.Column(sa.JSON(None))
    dismissed = sa.Column(sa.Boolean())
    uuid = sa.Column(sa.Text())
    klass = sa.Column(sa.Text())


@dataclass(kw_only=True)
class AlertSourceRunFailedAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.CRITICAL,
        title="Alert Check Failed",
        text="Failed to check for alert %(source_name)s: %(traceback)s",
        exclude_from_list=True,
    )
    source_name: str
    traceback: str


@dataclass(kw_only=True)
class AlertSourceRunFailedOnBackupNodeAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.CRITICAL,
        title="Alert Check Failed (Standby Controller)",
        text="Failed to check for alert %(source_name)s on standby controller: %(traceback)s",
        exclude_from_list=True,
    )
    source_name: str
    traceback: str


@dataclass(kw_only=True)
class AutomaticAlertFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="Failed to Notify TrueNAS About Alert",
        text=textwrap.dedent("""\
            Creating an automatic alert for TrueNAS about system %(serial)s failed: %(error)s.
            Please contact TrueNAS Support: https://www.truenas.com/support/

            Alert:

            %(alert)s
        """),
        exclude_from_list=True,
        deleted_automatically=False,
    )
    serial: str
    error: str
    alert: str
