from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass


class GlusterdWorkdirUnavailAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.CLUSTERING
    level = AlertLevel.CRITICAL
    title = "Glusterd peer information is unavailable"
    text = "Glusterd work directory dataset is not mounted."

    async def delete(self, alerts, query):
        return []


class GlusterdUUIDChangedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.CLUSTERING
    level = AlertLevel.CRITICAL
    title = "Glusterd UUID changed"
    text = "Glusterd host UUID changed unexpectedly."

    async def delete(self, alerts, query):
        return []
