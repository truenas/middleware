from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass


class JBOFTearDownFailureAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "JBOF removal may require reboot"
    text = "Incomplete removal of JBOF requires a reboot to cleanup."

    async def delete(self, alerts, query):
        return []
