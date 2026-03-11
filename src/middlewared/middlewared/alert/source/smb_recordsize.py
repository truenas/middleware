from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, OneShotAlertClass


class SMBVeeamFastCloneAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    keys = []
    title = "SMB shares use incorrect recordsize value for Veeam Fast Clone"
    text = "SMB shares cannot use Veeam Fast Clone due to incorrect ZFS recordsize: %(shares)s"
