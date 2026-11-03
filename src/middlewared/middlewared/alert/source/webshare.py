from middlewared.alert.applicability import NOT_APPLIANCE_HARDWARE
from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass


class WebshareStoppedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="Webshare Stopped",
        text=(
            "Webshare was stopped because TrueNAS Connect is not configured. It will start automatically once"
            " TrueNAS Connect is configured."
        ),
        deleted_automatically=False,
        keys=[],
        applies_to=NOT_APPLIANCE_HARDWARE,
    )
