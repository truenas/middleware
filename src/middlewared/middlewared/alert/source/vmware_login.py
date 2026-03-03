from middlewared.alert.base import AlertClass, AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass


class VMWareLoginFailedAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.WARNING,
        title="VMWare Login Failed",
        text="VMWare login to %(hostname)s failed: %(error)s.",
    )

    @classmethod
    def key(cls, args):
        return args['hostname']
