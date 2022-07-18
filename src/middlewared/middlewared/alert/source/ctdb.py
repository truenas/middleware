from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass


class CtdbInitFailAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.CLUSTERING
    level = AlertLevel.WARNING
    title = "CTDB service initialization failed"
    text = "CTDB service initialization failed: %(errmsg)s"

    async def delete(self, alerts, query):
        return []


class CtdbClusteredServiceAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.CLUSTERING
    level = AlertLevel.WARNING
    title = "Clustered service start failed"
    text = "Clustered service start failed: %(errmsg)s"

    async def delete(self, alerts, query):
        return []
