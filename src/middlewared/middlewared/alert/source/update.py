from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, FilePresenceAlertSource
from middlewared.plugins.update_.utils import UPDATE_FAILED_SENTINEL


class UpdateFailedAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "Update Failed"
    text = "Update failed. See /data/update.failed for details."


class UpdateFailedAlertSource(FilePresenceAlertSource):
    path = UPDATE_FAILED_SENTINEL
    klass = UpdateFailedAlertClass
