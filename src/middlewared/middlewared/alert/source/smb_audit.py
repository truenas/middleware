from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass


class SMBAuditShareDisabledAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "SMB share audit configuration contains invalid groups"
    text = "SMB shares disabled due to invalid group in audit configuration: %(shares)s"

    async def delete(self, alerts, query):
        return []
