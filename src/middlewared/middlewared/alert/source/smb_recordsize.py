from dataclasses import dataclass

from middlewared.alert.base import AlertCategory, AlertClass, AlertClassConfig, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class SMBVeeamFastCloneAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="SMB shares use incorrect recordsize value for Veeam Fast Clone",
        text="SMB shares cannot use Veeam Fast Clone due to incorrect ZFS recordsize: %(shares)s",
        keys=[],
    )

    shares: str
