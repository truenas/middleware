from middlewared.alert.base import AlertClass, OneShotAlertClass, AlertCategory, AlertLevel

URL = "https://www.truenas.com/docs/scale/scaledeprecatedfeatures/"


class DeprecatedServiceConfigurationAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "Deprecated Service Configuration Detected"
    text = (
        "The following service configuration is deprecated %(config)s. "
        "This functionality is scheduled for removal in a future version of SCALE. "
        f"Before upgrading, please check {URL} for more information."
    )

    def key(self, args):
        return args['config']
