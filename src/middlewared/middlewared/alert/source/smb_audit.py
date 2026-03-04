from dataclasses import dataclass

from middlewared.alert.base import AlertCategory, AlertClass, AlertClassConfig, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class SMBAuditShareDisabledAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="SMB share audit configuration contains invalid groups",
        text="SMB shares disabled due to invalid group in audit configuration: %(shares)s",
        keys=[],
    )

    shares: str
