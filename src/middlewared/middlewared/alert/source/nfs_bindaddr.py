from middlewared.alert.base import AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel


class NFSBindAddressAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = "NFS Services Could Not Bind to Specific IP Addresses, Using 0.0.0.0"
    text = "NFS services could not bind to specific IP addresses, using 0.0.0.0."
