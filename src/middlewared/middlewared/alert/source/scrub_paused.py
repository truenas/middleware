from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import CrontabSchedule


class ScrubPausedAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "Scrub Is Paused"
    text = "Scrub for pool %r is paused."


class ScrubPausedAlertSource(ThreadedAlertSource):
    schedule = CrontabSchedule(hour=3)

    async def check(self):
        alerts = []
        for pool in await self.middleware.call("zfs.pool.pools_with_paused_scrubs"):
            alerts.append(Alert(ScrubPausedAlertClass, pool.name))
        return alerts
