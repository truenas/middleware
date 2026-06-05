from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import typing
from typing import Any

from middlewared.alert.base import Alert, AlertSource

if typing.TYPE_CHECKING:
    from collections.abc import Callable

POLICIES: list[str] = ["IMMEDIATELY", "HOURLY", "DAILY", "NEVER"]
DEFAULT_POLICY: str = "IMMEDIATELY"
# The below value come from observation from support of how long an M-series boot can take.
FAILOVER_ALERTS_BACKOFF_SECS: int = 900


@dataclass(slots=True, frozen=True, kw_only=True)
class AlertFailoverInfo:
    this_node: str
    other_node: str
    run_on_backup_node: bool
    run_failover_related: bool


@dataclass(slots=True, frozen=True)
class AlertSourceLock:
    source_name: str
    expires_at: float


class AlertPolicy:
    def __init__(self, key: Callable[[datetime], Any] = lambda now: now) -> None:
        self.key = key
        self.last_key_value: Any = None
        self.last_key_value_alerts: dict[str, Alert[Any]] = {}

    def receive_alerts(self, now: datetime, alerts: list[Alert[Any]]) -> tuple[list[Alert[Any]], list[Alert[Any]]]:
        alerts_by_uuid = {alert.uuid: alert for alert in alerts}
        gone_alerts: list[Alert[Any]] = []
        new_alerts: list[Alert[Any]] = []
        key = self.key(now)
        if key != self.last_key_value:
            gone_alerts = [alert for alert in self.last_key_value_alerts.values() if alert.uuid not in alerts_by_uuid]
            new_alerts = [alert for alert in alerts_by_uuid.values() if alert.uuid not in self.last_key_value_alerts]

            self.last_key_value = key
            self.last_key_value_alerts = alerts_by_uuid

        return gone_alerts, new_alerts

    def delete_alert(self, alert: Alert[Any]) -> None:
        self.last_key_value_alerts.pop(alert.uuid, None)


def _default_source_run_times() -> dict[str, Any]:
    return {"last": [], "max": 0, "total_count": 0, "total_time": 0}


class AlertState:
    """Mutable in-memory runtime state for the ``alert`` service.

    There is intentionally no internal locking here: every mutation happens on the asyncio event
    loop, and the long-running operations that rebuild/scan ``alerts`` are serialized by the shared
    ``process_alerts`` job lock. See ``ALERT_TYPESAFE_REFACTOR_PLAN.md`` for the concurrency
    analysis.
    """

    def __init__(self, alert_sources: dict[str, AlertSource]) -> None:
        self.alert_sources = alert_sources
        self.alerts: list[Alert[Any]] = []
        self.blocked_sources: defaultdict[str, set[str]] = defaultdict(set)
        self.sources_locks: dict[str, AlertSourceLock] = {}
        self.blocked_failover_alerts_until: float = 0.0
        self.sources_run_times: defaultdict[str, dict[str, Any]] = defaultdict(_default_source_run_times)
        self.node: str = "A"
        self.alert_source_last_run: defaultdict[str, datetime] = defaultdict(lambda: datetime.min)
        self.policies: dict[str, AlertPolicy] = {}
        self.alert_sources_errors: set[str] = set()
        self.send_alerts_on_ready: bool = False
