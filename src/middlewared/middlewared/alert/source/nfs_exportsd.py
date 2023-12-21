from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass


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
    text = "NFS export for %(path)r contains names that are invalid: %(names)s"

    async def create(self, args):
        return Alert(NFSexportMappingInvalidNamesAlertClass, args, key=args['id'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.args['id'] != query,
            alerts
        ))
