from dataclasses import dataclass

from middlewared.alert.base import AlertClass, AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class VMWareLoginFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.WARNING,
        title="VMWare Login Failed",
        text="VMWare login to %(hostname)s failed: %(error)s.",
    )

    hostname: str
    error: str

    @classmethod
    def key(cls, args):
        return args['hostname']
