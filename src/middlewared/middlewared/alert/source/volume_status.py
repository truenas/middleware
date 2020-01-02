import logging

from middlewared.alert.base import Alert, AlertLevel, AlertSource

log = logging.getLogger("volume_status_alert")


class VolumeStatusAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "Pool Status Is Not Healthy"

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
                    "Pool %(volume)s state is %(state)s: %(status)s",
                    {
                        "volume": pool["name"],
                        "state": state,
                        "status": status,
                    }
                ))

        return alerts

    async def enabled(self):
        if not (await self.middleware.call("system.is_freenas")):
            try:
                status = await self.middleware.call("notifier.failover_status")
                return status in ("MASTER", "SINGLE")
            except Exception as e:
                log.debug(f'notifier.failover_status failed with error: {e}')
                return False
        return True
