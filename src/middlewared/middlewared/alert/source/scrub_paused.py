from datetime import datetime, timedelta

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource


class ScrubPausedAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "Scrub Is Paused"
    text = "Scrub for pool %r is paused for more than 8 hours."


class ScrubPausedAlertSource(ThreadedAlertSource):
    async def check(self):
        alerts = []
        for pool in await self.middleware.call("pool.query"):
            if pool["scan"]["pause"] is not None:
                if pool["scan"]["pause"] < datetime.now() - timedelta(hours=8):
                    alerts.append(Alert(ScrubPausedAlertClass, pool["name"]))
        return alerts
