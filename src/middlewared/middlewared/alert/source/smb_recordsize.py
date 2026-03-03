from middlewared.alert.base import AlertCategory, AlertClass, AlertClassConfig, AlertLevel, OneShotAlertClass


class SMBVeeamFastCloneAlertClass(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="SMB shares use incorrect recordsize value for Veeam Fast Clone",
        text="SMB shares cannot use Veeam Fast Clone due to incorrect ZFS recordsize: %(shares)s",
        keys=[],
    )
