from datetime import timedelta
import os
import json
import logging

from freenasOS.Update import PendingUpdates
from freenasUI.system.utils import is_update_applied

from middlewared.alert.base import Alert, AlertLevel, AlertSource, FilePresenceAlertSource, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

UPDATE_APPLIED_SENTINEL = "/tmp/.updateapplied"

log = logging.getLogger("update_check_alertmod")


class TrainEOLAlertSource(AlertSource):
    level = AlertLevel.INFO
    title = "Update Train EOL Reached"
    text = ("The FreeNAS 11.2-STABLE update train has reached its End of "
            "Life and is no longer receiving security updates. Please "
            "schedule a time to upgrade to FreeNAS 11.3 and use the "
            "FreeNAS 11.3-STABLE update train. For more details about "
            "updating FreeNAS, please refer to the FreeNAS Documentation "
            "(https://www.ixsystems.com/documentation/freenas/11.3-RELEASE/"
            "system.html#update)")

    async def check(self):
        return Alert()


class HasUpdateAlertSource(ThreadedAlertSource):
    level = AlertLevel.INFO
    title = "Update Available"

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

        path = self.middleware.call_sync("notifier.get_update_location")
        if not path:
            return

        try:
            updates = PendingUpdates(path)
        except Exception:
            updates = None

        if updates:
            return Alert("A system update is available. Go to System -> Update to download and apply the update.")


class UpdateAppliedAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "Update Not Applied"

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
    title = "Update Failed"
    text = "Update failed. Check /data/update.failed for further details"

    schedule = IntervalSchedule(timedelta(hours=1))

    path = "/data/update.failed"
