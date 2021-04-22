from middlewared.alert.base import AlertClass, OneShotAlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource


class VMWareLoginFailedAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.WARNING
    title = "VMWare Login Failed"
    text = "VMWare login to %(hostname)s failed: %(error)s."

    async def create(self, args):
        return Alert(VMWareLoginFailedAlertClass, args)

    async def delete(self, alerts, query):
        hostname = query

        return list(filter(
            lambda alert: alert.args["hostname"] != hostname,
            alerts
        ))
