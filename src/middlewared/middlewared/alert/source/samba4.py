import os

from middlewared.alert.base import Alert, AlertLevel, AlertSource


class Samba4AlertSource(AlertSource):
    level = AlertLevel.WARNING
    title = "Samba error"

    async def check(self):
        if not await self.middleware.call("datastore.query", "storage.volume"):
            return

        try:
            if await self.middleware.call("notifier.failover_status") == "BACKUP":
                return
        except Exception:
            return

        systemdataset = await self.middleware.call("systemdataset.config")
        if not systemdataset["pool"]:
            return Alert(
                "No system pool configured, please configure one in "
                "Settings -> System Dataset -> Pool"
            )

        if os.path.exists("/var/db/samba4/.alert_cant_migrate"):
            return Alert(
                "Multiple legacy samba4 datasets detected. Auto-migration "
                "to /mnt/%s/.system/samba4 cannot be done. Please perform "
                "this step manually and then delete the now-obsolete "
                "samba4 datasets and /var/db/samba4/.alert_cant_migrate",
                systemdataset["pool"]
            )
