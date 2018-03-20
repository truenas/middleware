from middlewared.alert.base import Alert, AlertLevel, AlertSource


class VolumeStatusAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "The volume status is not HEALTHY"

    hardware = True

    async def check(self):
        if not await self.enabled():
            return

        alerts = []
        for pool in await self.middleware.call("pool.query"):
            if not pool["is_decrypted"]:
                continue

            state, status = await self.middleware.call("notifier.zpool_status", pool["name"])
            if state != "HEALTHY":
                if not (await self.middleware.call("system.is_freenas")):
                    try:
                        await self.middleware.call("notifier.zpool_enclosure_sync", pool["name"])
                    except Exception:
                        pass

                alerts.append(Alert(
                    "The volume %(volume)s state is %(state)s: %(status)s",
                    {
                        "volume": pool["name"],
                        "state": state,
                        "status": status,
                    }
                ))

        return alerts

    async def enabled(self):
        if not (await self.middleware.call("system.is_freenas")):
            status = await self.middleware.call("notifier.failover_status")
            return status in ("MASTER", "SINGLE")

        return True
