import os

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class NoSystemPoolConfiguredAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "No System Dataset Pool Configured"
    text = "The system dataset has not been set. Please choose a pool in System -> System Dataset."


class SambaDatasetAutoMigrationCantBeDoneAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "Samba Auto-Migration to System Dataset Failed"
    text = (
        "Multiple legacy Samba4 datasets detected. Auto-migration "
        "to /mnt/%s/.system/samba4 cannot be done. Please perform "
        "this step manually and then delete the now-obsolete "
        "Samba4 datasets and the file /var/db/samba4/.alert_cant_migrate."
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
