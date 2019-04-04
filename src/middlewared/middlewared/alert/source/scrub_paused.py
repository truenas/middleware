import libzfs

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.alert.schedule import CrontabSchedule


class ScrubPausedAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "Scrub Is Paused"
    text = "Scrub for pool %r is paused."


class ScrubPausedAlertSource(ThreadedAlertSource):
    schedule = CrontabSchedule(hour=3)

    def check_sync(self):
        alerts = []
        with libzfs.ZFS() as zfs:
            for pool in zfs.pools:
                if pool.scrub.pause is not None:
                    alerts.append(Alert(ScrubPausedAlertClass, pool.name))
        return alerts
