from dataclasses import dataclass

from middlewared.alert.base import AlertCategory, AlertClassConfig, OneShotAlertClass, AlertLevel


@dataclass(kw_only=True)
class FailoverRebootAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="Failover Event Caused System Reboot",
        text=(
            "%(fqdn)s had a failover event. The system was rebooted to ensure a "
            "proper failover occurred. The operating system successfully came "
            "back online at %(now)s."
        ),
        keys=[],
    )

    fqdn: str
    now: str


@dataclass(kw_only=True)
class FencedRebootAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="Fenced Caused System Reboot",
        text=(
            '%(fqdn)s had a failover event. The system was rebooted because persistent '
            'SCSI reservations were lost and/or cleared. The operating system successfully '
            'came back online at %(now)s.'
        ),
        keys=[],
    )

    fqdn: str
    now: str
