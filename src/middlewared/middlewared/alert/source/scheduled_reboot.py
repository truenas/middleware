from dataclasses import dataclass

from middlewared.alert.applicability import HA_LICENSED
from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class FailoverRebootAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HA,
        level=AlertLevel.WARNING,
        title="Failover Event Caused System Reboot",
        text=(
            "%(fqdn)s had a failover event. The system was rebooted to ensure a "
            "proper failover occurred. The operating system successfully came "
            "back online at %(now)s."
        ),
        applies_to=HA_LICENSED,
        keys=[],
    )

    fqdn: str
    now: str


@dataclass(kw_only=True)
class FencedRebootAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HA,
        level=AlertLevel.WARNING,
        title="Fenced Caused System Reboot",
        text=(
            '%(fqdn)s had a failover event. The system was rebooted because persistent '
            'SCSI reservations were lost and/or cleared. The operating system successfully '
            'came back online at %(now)s.'
        ),
        applies_to=HA_LICENSED,
        keys=[],
    )

    fqdn: str
    now: str
