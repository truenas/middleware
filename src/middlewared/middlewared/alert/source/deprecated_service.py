import json
from middlewared.alert.base import Alert, AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel


class DeprecatedServiceAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "Deprecated Service is Running"
    text = "The following running service is deprecated and will be removed in a future release: %(service)s"

    async def create(self, args):
        return Alert(DeprecatedServiceAlertClass, args, key=args['service'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: json.loads(alert.key) != str(query),
            alerts
        ))
