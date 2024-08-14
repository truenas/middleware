from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass


class AdminSessionActiveAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Active administrator session on TrueNAS server"
    text = (
        "System administrator (root or truenas_admin) has one or more "
        "active sessions on the TrueNAS server with the following session ids: %(sessions)s"
    )

    async def delete(self, alerts, query):
        return []
