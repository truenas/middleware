from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass


class NFSblockedByExportsDirAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.ERROR
    title = "NFS start is blocked by entries in /etc/exports.d"
    text = "/etc/exports.d contains entries that must be removed: %(entries)s"

    async def delete(self, alerts, query):
        return []


class NFSexportMappingInvalidNamesAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.ERROR
    title = "NFS export entry blocked"
    text = "NFS shares have invalid names:\n%(share_list)s"

    async def delete(self, alerts, query):
        return []
