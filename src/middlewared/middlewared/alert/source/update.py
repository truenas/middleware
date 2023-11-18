from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, FilePresenceAlertSource
from middlewared.plugins.update_.utils import UPDATE_FAILED_SENTINEL


class UpdateFailedAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "Update Failed"
    text = f"Update failed. See {UPDATE_FAILED_SENTINEL} for details."


class UpdateFailedAlertSource(FilePresenceAlertSource):
    path = UPDATE_FAILED_SENTINEL
    klass = UpdateFailedAlertClass
