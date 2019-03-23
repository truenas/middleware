from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class VolumeStatusAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.CRITICAL
    title = "Pool Status Is Not Healthy"
    text = "Pool %(volume)s state is %(state)s: %(status)s."

    hardware = True


class VolumeStatusAlertSource(AlertSource):
    async def check(self):
        if not await self.enabled():
            return

        alerts = []
        for pool in await self.middleware.call("pool.query"):
            if not pool["is_decrypted"]:
                continue

            if not pool['healthy']:
                if not (await self.middleware.call("system.is_freenas")):
                    try:
                        await self.middleware.call("enclosure.sync_zpool", pool["name"])
                    except Exception:
                        pass

                alerts.append(Alert(
                    VolumeStatusAlertClass,
                    {
                        "volume": pool["name"],
                        "state": pool["status"],
                        "status": pool["status_detail"],
                    }
                ))

        return alerts

    async def enabled(self):
        if not (await self.middleware.call("system.is_freenas")):
            status = await self.middleware.call("failover.status")
            return status in ("MASTER", "SINGLE")

        return True
