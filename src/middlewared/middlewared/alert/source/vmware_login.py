from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, SimpleOneShotAlertClass


class VMWareLoginFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.WARNING
    title = "VMWare Login Failed"
    text = "VMWare login to %(hostname)s failed: %(error)s."

    def key(self, args):
        return args['hostname']
