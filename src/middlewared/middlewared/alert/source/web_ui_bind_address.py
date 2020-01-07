from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, OneShotAlertClass


class WebUiBindAddressV2AlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "The Web Interface Сould Not Bind to Configured Address"
    text = "The Web interface could not bind to %(addresses)s. Using %(wildcard)s instead."

    async def create(self, args):
        return Alert(self.__class__, args)

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.args["family"] != query,
            alerts
        ))
