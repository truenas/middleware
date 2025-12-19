from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.plugins.zfs_.zfs_events import VOLUME_STATUS_ALERTS
from middlewared.utils.zfs import query_imported_fast_impl


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

        try:
            states = await self.middleware.call("cache.get", "VolumeStatusAlertSource.pools_states")
        except KeyError:
            states = None

        current_states = await self.middleware.run_in_thread(query_imported_fast_impl)
        await self.middleware.call("cache.put", "VolumeStatusAlertSource.pools_states", current_states)

        alerts = None
        if current_states == states:
            try:
                alerts = await self.middleware.call("cache.get", VOLUME_STATUS_ALERTS)
            except KeyError:
                pass

        if alerts is None:
            alerts = []
            boot_pool = await self.middleware.call("boot.pool_name")
            for pool in await self.middleware.call("zfs.pool.query", [["id", "=", boot_pool]]):
                if not pool["healthy"]:
                    alerts.append([
                        "BootPoolStatusAlertClass",
                        {
                            "status": pool["status"],
                            "status_detail": pool["status_detail"],
                        },
                    ])
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

                    alerts.append([
                        "VolumeStatusAlertClass",
                        {
                            "volume": pool["name"],
                            "state": pool["status"],
                            "status": pool["status_detail"],
                            "devices": devices,
                        }
                    ])

            await self.middleware.call("cache.put", VOLUME_STATUS_ALERTS, alerts)

        return [
            Alert(
                {
                    "BootPoolStatusAlertClass": BootPoolStatusAlertClass,
                    "VolumeStatusAlertClass": VolumeStatusAlertClass,
                }[alert[0]],
                alert[1]
            )
            for alert in alerts
        ]

    async def enabled(self):
        if await self.middleware.call("system.is_enterprise"):
            status = await self.middleware.call("failover.status")
            return status in ("MASTER", "SINGLE")

        return True
