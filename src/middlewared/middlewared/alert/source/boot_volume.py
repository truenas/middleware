from middlewared.alert.base import Alert, AlertLevel, AlertSource


class BootVolumeStatusAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "The boot volume state is not HEALTHY"

    hardware = True

    async def check(self):
        state, status = await self.middleware.call("notifier.zpool_status", "freenas-boot")
        if state != "HEALTHY":
            return Alert(
                "The boot volume state is %(state)s: %(status)s",
                {
                    "state": state,
                    "status": status,
                },
            )
