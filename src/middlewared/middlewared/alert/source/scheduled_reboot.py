from middlewared.alert.base import AlertCategory, AlertClass, AlertClassConfig, OneShotAlertClass, AlertLevel


class FailoverRebootAlert(AlertClass, OneShotAlertClass):
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


class FencedRebootAlert(AlertClass, OneShotAlertClass):
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
