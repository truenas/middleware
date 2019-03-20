from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class BootVolumeStatusAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "The boot volume status is not HEALTHY"
    text = "The boot volume status is %(state)s: %(status)s"

    hardware = True


class BootVolumeStatusAlertSource(AlertSource):
    async def check(self):
        pool = await self.middleware.call("zfs.pool.query", [["id", "=", "freenas-boot"]])
        if not pool:
            return
        pool = pool[0]
        if not pool["healthy"]:
            return Alert(
                BootVolumeStatusAlertClass,
                {
                    "state": pool["status"],
                    "status": pool["status_detail"],
                },
            )
