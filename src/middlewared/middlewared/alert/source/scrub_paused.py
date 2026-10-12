from datetime import timedelta
from typing import Any

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertSource,
    NonDataclassAlertClass,
)
from middlewared.utils.time_utils import utc_now


class ScrubPausedAlert(NonDataclassAlertClass[str], AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.WARNING,
        title="Scrub Is Paused",
        text="Scrub for pool %r is paused for more than 8 hours.",
    )


class ScrubPausedAlertSource(AlertSource):
    run_on_backup_node = False

    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        threshold = await self.middleware.call("pool.scrub.alert_threshold")
        alerts: list[Alert[Any]] = []
        for pool in await self.middleware.call("pool.query"):
            if pool["scan"] is not None:
                if pool["scan"]["pause"] is not None:
                    if pool["scan"]["pause"] <= utc_now(naive=False) - timedelta(hours=threshold):
                        alerts.append(Alert(ScrubPausedAlert(pool["name"])))
        return alerts
