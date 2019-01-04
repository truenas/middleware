from middlewared.alert.base import Alert, AlertLevel, AlertSource


class BootVolumeStatusAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "The boot volume state is not HEALTHY"

    hardware = True

    async def check(self):
        pool = await self.middleware.call("zfs.pool.query", [["id", "=", "freenas-boot"]])
        if not pool:
            return
        pool = pool[0]
        if not pool["healthy"]:
            return Alert(
                "The boot volume state is %(state)s: %(status)s",
                {
                    "state": pool["status"],
                    "status": pool["status_detail"],
                },
            )
