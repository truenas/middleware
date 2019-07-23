from datetime import timedelta
import os
import json
import logging

from freenasOS.Update import PendingUpdates
from freenasUI.system.utils import is_update_applied

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, FilePresenceAlertSource, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

UPDATE_APPLIED_SENTINEL = "/tmp/.updateapplied"

log = logging.getLogger("update_check_alertmod")


class HasUpdateAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.INFO
    title = "Update Available"
    text = "A system update is available. Go to System -> Update to download and apply the update."


class HasUpdateAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(timedelta(hours=1))

    run_on_backup_node = False

    def check_sync(self):
        try:
            self.middleware.call_sync("datastore.query", "system.update", None, {"get": True})
        except IndexError:
            self.middleware.call_sync("datastore.insert", "system.update", {
                "upd_autocheck": True,
                "upd_train": "",
            })

        path = self.middleware.call_sync("update.get_update_location")
        if not path:
            return

        try:
            updates = PendingUpdates(path)
        except Exception:
            updates = None

        if updates:
            return Alert(HasUpdateAlertClass)


class UpdateNotAppliedAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Update Not Applied"
    text = "%s"


class UpdateNotAppliedAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(timedelta(minutes=10))

    def check_sync(self):
        if os.path.exists(UPDATE_APPLIED_SENTINEL):
            try:
                with open(UPDATE_APPLIED_SENTINEL, "rb") as f:
                    data = json.loads(f.read().decode("utf8"))
            except Exception:
                log.error(
                    "Could not load UPDATE APPLIED SENTINEL located at {0}".format(
                        UPDATE_APPLIED_SENTINEL
                    ),
                    exc_info=True
                )
                return

            update_applied, msg = is_update_applied(data["update_version"], create_alert=False)
            if update_applied:
                return Alert(UpdateNotAppliedAlertClass, msg)


class UpdateFailedAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "Update Failed"
    text = "Update failed. See /data/update.failed for details."


class UpdateFailedAlertSource(FilePresenceAlertSource):
    path = "/data/update.failed"
    klass = UpdateFailedAlertClass
