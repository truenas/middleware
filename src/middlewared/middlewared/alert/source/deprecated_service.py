import json

from middlewared.alert.base import Alert, AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel

URL = "https://www.truenas.com/docs/scale/scaledeprecatedfeatures/"


class DeprecatedServiceAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "Deprecated Service is Running"
    text = (
        "The following active service is deprecated in SCALE Bluefin %(service)s"
        " This service is scheduled for removal in next SCALE major version (Cobia)."
        " Please plan to migrate these services to the equivalent SCALE application"
        " before upgrading to the next SCALE major version. For additional details"
        f" and migration tutorials, see {URL}."
    )

    async def create(self, args):
        return Alert(DeprecatedServiceAlertClass, args, key=args['service'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: json.loads(alert.key) != str(query),
            alerts
        ))
