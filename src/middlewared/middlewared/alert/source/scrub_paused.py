from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.utils.time_utils import time_now


class ScrubPausedAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "Scrub Is Paused"
    text = "Scrub for pool %r is paused for more than 8 hours."


class ScrubPausedAlertSource(ThreadedAlertSource):
    run_on_backup_node = False

    async def check(self):
        alerts = []
        for pool in await self.middleware.call("pool.query"):
            if pool["scan"] is not None:
                if pool["scan"]["pause"] is not None:
                    if pool["scan"]["pause"] < time_now() - timedelta(hours=8):
                        alerts.append(Alert(ScrubPausedAlertClass, pool["name"]))
        return alerts
