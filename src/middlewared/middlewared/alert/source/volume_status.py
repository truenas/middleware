from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class VolumeStatusAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.CRITICAL
    title = "Pool Status Is Not Healthy"
    text = "Pool %(volume)s state is %(state)s: %(status)s%(devices)s"
    proactive_support = True


class BootPoolStatusAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = "Boot Pool Is Not Healthy"
    text = "Boot pool status is %(status)s: %(status_detail)s."
    proactive_support = True


class VolumeStatusAlertSource(AlertSource):
    async def check(self):
        if not await self.enabled():
            return

        alerts = []
        for pool in await self.middleware.call("pool.query"):
            if not pool["healthy"] or (pool["warning"] and pool["status_code"] != "FEAT_DISABLED"):
                bad_vdevs = []
                if pool["topology"]:
                    for vdev in await self.middleware.call("pool.flatten_topology", pool["topology"]):
                        if vdev["type"] == "DISK" and vdev["status"] != "ONLINE":
                            name = vdev["guid"]
                            if vdev.get("unavail_disk"):
                                name = f'{vdev["unavail_disk"]["model"]} {vdev["unavail_disk"]["serial"]}'
                            bad_vdevs.append(f"Disk {name} is {vdev['status']}")
                if bad_vdevs:
                    devices = (f"<br>The following devices are not healthy:"
                               f"<ul><li>{'</li><li>'.join(bad_vdevs)}</li></ul>")
                else:
                    devices = ""

                alerts.append(Alert(
                    VolumeStatusAlertClass,
                    {
                        "volume": pool["name"],
                        "state": pool["status"],
                        "status": pool["status_detail"],
                        "devices": devices,
                    }
                ))

        return alerts

    async def enabled(self):
        if await self.middleware.call("system.is_enterprise"):
            status = await self.middleware.call("failover.status")
            return status in ("MASTER", "SINGLE")

        return True
