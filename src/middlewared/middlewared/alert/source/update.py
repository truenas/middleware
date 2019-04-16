from datetime import timedelta
import logging

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource, FilePresenceAlertSource, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

log = logging.getLogger("update_check_alertmod")


class HasUpdateAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.INFO
    title = "New Update Available"
    text = "A new update is available. Apply it with System -> Update."


class HasUpdateAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(timedelta(hours=1))

    def check_sync(self):
        try:
            self.middleware.call_sync("datastore.query", "system.update", None, {"get": True})
        except IndexError:
            self.middleware.call_sync("datastore.insert", "system.update", {
                "upd_autocheck": True,
                "upd_train": "",
            })

        if self.middleware.call_sync("update.get_pending"):
            return Alert(HasUpdateAlertClass)


class UpdateNotAppliedAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Update Applied Pending Reboot"
    text = "Update has been applied but is pending a reboot."


class UpdateNotAppliedAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=10))

    async def check(self):
        try:
            applied = await self.middleware.call('cache.get', 'update.applied')
        except KeyError:
            return
        if applied is True:
            return Alert(UpdateNotAppliedAlertClass)


class UpdateFailedAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "Update Failed"
    text = "Update failed. See /data/update.failed for details."


class UpdateFailedAlertSource(FilePresenceAlertSource):
    path = "/data/update.failed"
    klass = UpdateFailedAlertClass
