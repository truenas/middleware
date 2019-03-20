import os

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class NoSystemPoolConfiguredAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "No system dataset pool configured"
    text = "No system pool configured. Please configure one in Settings -> System Dataset -> Pool"


class SambaDatasetAutoMigrationCantBeDoneAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "Samba auto-migration to system dataset failed"
    text = (
        "Multiple legacy samba4 datasets detected. Auto-migration "
        "to /mnt/%s/.system/samba4 cannot be done. Please perform "
        "this step manually and then delete the now-obsolete "
        "samba4 datasets and /var/db/samba4/.alert_cant_migrate"
    )


class Samba4AlertSource(AlertSource):
    async def check(self):
        if not await self.middleware.call("datastore.query", "storage.volume"):
            return

        try:
            if await self.middleware.call("failover.status") == "BACKUP":
                return
        except Exception:
            return

        systemdataset = await self.middleware.call("systemdataset.config")
        if not systemdataset["pool"]:
            return Alert(NoSystemPoolConfiguredAlertClass)

        if os.path.exists("/var/db/samba4/.alert_cant_migrate"):
            return Alert(SambaDatasetAutoMigrationCantBeDoneAlertClass, systemdataset["pool"])
