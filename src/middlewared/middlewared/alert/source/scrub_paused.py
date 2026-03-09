from datetime import datetime, timedelta
from typing import Any

from middlewared.alert.base import (
    AlertClass, AlertClassConfig, AlertCategory, AlertLevel, Alert, NonDataclassAlertClass, ThreadedAlertSource,
)


class ScrubPausedAlert(NonDataclassAlertClass[str], AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.WARNING,
        title="Scrub Is Paused",
        text="Scrub for pool %r is paused for more than 8 hours.",
    )


class ScrubPausedAlertSource(ThreadedAlertSource):
    run_on_backup_node = False

    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        alerts: list[Alert[Any]] = []
        for pool in await self.middleware.call("pool.query"):
            if pool["scan"] is not None:
                if pool["scan"]["pause"] is not None:
                    if pool["scan"]["pause"] < datetime.now() - timedelta(hours=8):
                        alerts.append(Alert(ScrubPausedAlert(pool["name"])))
        return alerts
