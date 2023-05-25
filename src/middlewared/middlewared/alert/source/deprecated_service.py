from middlewared.alert.base import Alert, AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel

URL = "https://www.truenas.com/docs/scale/scaledeprecatedfeatures/"


class DeprecatedServiceAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "Deprecated Service is Running"
    text = (
        "The following active service is deprecated %(service)s."
        " This service is scheduled for removal in a future SCALE version."
        " Please plan to migrate this service to the equivalent SCALE application"
        " before upgrading to the next version of SCALE. For additional details"
        f" and migration tutorials, see {URL}."
    )

    async def create(self, args):
        return Alert(DeprecatedServiceAlertClass, args, key=args['service'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.args['service'] != query,
            alerts
        ))
