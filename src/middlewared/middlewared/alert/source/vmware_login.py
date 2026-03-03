from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, OneShotAlertClass


class VMWareLoginFailedAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.WARNING
    title = "VMWare Login Failed"
    text = "VMWare login to %(hostname)s failed: %(error)s."

    def key(self, args):
        return args['hostname']
