from datetime import timedelta
import os
import json
import logging

try:
    from freenasOS import Update
    from freenasOS.Update import PendingUpdates
except ImportError:
    Update = PendingUpdates = None

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, FilePresenceAlertSource, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

UPDATE_APPLIED_SENTINEL = "/tmp/.updateapplied"

log = logging.getLogger("update_check_alertmod")


class HasUpdateAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.INFO
    title = "Update Available"
    text = "A system update is available. Go to System -> Update to download and apply the update."


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

            if is_update_applied:
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
