from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass


class SMBVeeamFastCloneAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "SMB shares use incorrect recordsize value for Veeam Fast Clone"
    text = "SMB shares cannot use Veeam Fast Clone due to incorrect ZFS recordsize: %(shares)s"

    async def delete(self, alerts, query):
        return []
