from middlewared.alert.applicability import NOT_APPLIANCE_HARDWARE
from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, OneShotAlertClass


class WebshareStoppedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "Webshare Stopped"
    text = (
        "Webshare was stopped because TrueNAS Connect is not configured. It will start automatically once"
        " TrueNAS Connect is configured."
    )
    applies_to = NOT_APPLIANCE_HARDWARE

    async def create(self, args):
        return Alert(WebshareStoppedAlertClass, args)

    async def delete(self, alerts, query):
        return []
