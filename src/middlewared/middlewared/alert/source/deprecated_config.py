import json

from middlewared.alert.base import Alert, AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel

URL = "https://www.truenas.com/docs/scale/scaledeprecatedfeatures/"


class DeprecatedServiceConfigurationAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "Deprecated Service Configuration Detected"
    text = (
        "The following service configuration is deprecated %(config)s. "
        "This functionality is scheduled for removal in a future version of SCALE. "
        f"Before upgrading, please check {URL} for more information."
    )

    async def create(self, args):
        return Alert(DeprecatedServiceConfigurationAlertClass, args, key=args['config'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: json.loads(alert.key) != str(query),
            alerts
        ))
