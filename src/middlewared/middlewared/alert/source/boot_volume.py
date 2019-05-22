from middlewared.alert.base import Alert, AlertLevel, AlertSource


class BootVolumeStatusAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "Boot Pool Status Is Not Healthy"

    hardware = True

    async def check(self):
        state, status = await self.middleware.call("notifier.zpool_status", "freenas-boot")
        if state != "HEALTHY":
            return Alert(
                "Boot Pool Status Is %(state)s: %(status)s",
                {
                    "state": state,
                    "status": status,
                },
            )
