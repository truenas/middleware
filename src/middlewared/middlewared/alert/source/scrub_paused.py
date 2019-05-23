from middlewared.alert.base import Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import CrontabSchedule


class ScrubPausedAlertSource(AlertSource):
    level = AlertLevel.WARNING
    title = "Scrub Is Paused"

    schedule = CrontabSchedule(hour=3)

    async def check(self):
        alerts = []
        for pool in await self.middleware.call("zfs.pool.pools_with_paused_scrubs"):
            alerts.append(Alert(title="Scrub for pool %r is paused",
                                args=pool,
                                key=[pool]))
        return alerts
