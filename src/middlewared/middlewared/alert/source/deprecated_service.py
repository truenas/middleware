from middlewared.alert.base import AlertClass, AlertClassConfig, OneShotAlertClass, AlertCategory, AlertLevel

URL = "https://www.truenas.com/docs/scale/scaledeprecatedfeatures/"


class DeprecatedServiceAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="Deprecated Service is Running",
        text=(
            "The following active service is deprecated %(service)s. "
            "This service is scheduled for removal in a future version of SCALE. "
            f"Before upgrading, please check {URL} to confirm whether or not "
            "the service has been removed in the next version of SCALE."
        ),
    )

    @classmethod
    def key(cls, args):
        return args['service']
