import logging

try:
    from freenasOS import Update
    from freenasOS.Update import PendingUpdates
except ImportError:
    Update = PendingUpdates = None

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, FilePresenceAlertSource


log = logging.getLogger("update_check_alertmod")


class HasUpdateAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.INFO
    title = "Update Available"
    text = "A system update is available. Go to System -> Update to download and apply the update."


class UpdateFailedAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "Update Failed"
    text = "Update failed. See /data/update.failed for details."


class UpdateFailedAlertSource(FilePresenceAlertSource):
    path = "/data/update.failed"
    klass = UpdateFailedAlertClass
