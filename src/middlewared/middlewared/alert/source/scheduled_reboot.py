from middlewared.alert.base import AlertCategory, AlertClass, SimpleOneShotAlertClass, AlertLevel


class FailoverRebootAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    keys = []
    title = "Failover Event Caused System Reboot"
    text = (
        "%(fqdn)s had a failover event. The system was rebooted to ensure a "
        "proper failover occurred. The operating system successfully came "
        "back online at %(now)s."
    )


class FencedRebootAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    keys = []
    title = "Fenced Caused System Reboot"
    text = (
        '%(fqdn)s had a failover event. The system was rebooted because persistent '
        'SCSI reservations were lost and/or cleared. The operating system successfully '
        'came back online at %(now)s.'
    )
