import libzfs

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource
from middlewared.alert.schedule import CrontabSchedule


class ScrubPausedAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "Scrub is paused"

    schedule = CrontabSchedule(hour=3)

    def check_sync(self):
        alerts = []
        with libzfs.ZFS() as zfs:
            for pool in zfs.pools:
                if pool.scrub.pause is not None:
                    alerts.append(Alert(title="Scrub for pool %r is paused",
                                        args=pool.name,
                                        key=[pool.name]))
        return alerts
