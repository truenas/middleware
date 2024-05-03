from datetime import timedelta

from middlewared.alert.base import Alert, AlertClass, AlertCategory, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


class HasUpdateAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.INFO
    title = "Update Available"
    text = "A system update is available. Go to System Settings → Update to download and apply the update."


class HasUpdateAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=1))
    run_on_backup_node = False

    async def check(self):
        try:
            if (await self.middleware.call("update.check_available"))["status"] == "AVAILABLE":
                return Alert(HasUpdateAlertClass)
        except Exception:
            pass
