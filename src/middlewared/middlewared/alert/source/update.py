from datetime import timedelta
import os
import json
import logging

from freenasOS.Update import PendingUpdates
from freenasUI.system.utils import is_update_applied

from middlewared.alert.base import Alert, AlertLevel, FilePresenceAlertSource, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

UPDATE_APPLIED_SENTINEL = "/tmp/.updateapplied"

log = logging.getLogger("update_check_alertmod")


class HasUpdateAlertSource(ThreadedAlertSource):
    level = AlertLevel.INFO
    title = "There is a new update available"

    schedule = IntervalSchedule(timedelta(hours=1))

    def check_sync(self):
        try:
            self.middleware.call_sync("datastore.query", "system.update", None, {"get": True})
        except IndexError:
            self.middleware.call_sync("datastore.insert", "system.update", {
                "upd_autocheck": True,
                "upd_train": "",
            })

        path = self.middleware.call_sync("notifier.get_update_location")
        if not path:
            return

        try:
            updates = PendingUpdates(path)
        except Exception:
            updates = None

        if updates:
            return Alert("There is a new update available! Apply it in System -> Update tab.")


class UpdateAppliedAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "Update not applied"

    schedule = IntervalSchedule(timedelta(minutes=10))

    def check_sync(self):
        if os.path.exists(UPDATE_APPLIED_SENTINEL):
            try:
                with open(UPDATE_APPLIED_SENTINEL, "rb") as f:
                    data = json.loads(f.read().decode("utf8"))
            except:
                log.error(
                    "Could not load UPDATE APPLIED SENTINEL located at {0}".format(
                        UPDATE_APPLIED_SENTINEL
                    ),
                    exc_info=True
                )
                return

            update_applied, msg = is_update_applied(data["update_version"], create_alert=False)
            if update_applied:
                return Alert(msg)


class UpdateFailedAlertSource(FilePresenceAlertSource):
    level = AlertLevel.CRITICAL
    title = "Update failed. Check /data/update.failed for further details"

    schedule = IntervalSchedule(timedelta(hours=1))

    path = "/data/update.failed"
