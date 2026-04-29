from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass


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
    def key_from_args(cls, args: Any) -> Any:
        return args["hostname"]
