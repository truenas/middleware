from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.alert.schedule import CrontabSchedule


class BootPoolStatusAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "Boot Pool Is Not Healthy"
    text = "Boot pool status is %(status)s: %(status_detail)s."

    proactive_support = True


class BootPoolStatusAlertSource(AlertSource):

    schedule = CrontabSchedule(hour=1)

    async def check(self):
        boot_pool = await self.middleware.call("boot.pool_name")
        pool = await self.middleware.call("zfs.pool.query", [["id", "=", boot_pool]])
        if not pool:
            return
        pool = pool[0]
        if not pool["healthy"]:
            return Alert(
                BootPoolStatusAlertClass,
                {
                    "status": pool["status"],
                    "status_detail": pool["status_detail"],
                },
            )
