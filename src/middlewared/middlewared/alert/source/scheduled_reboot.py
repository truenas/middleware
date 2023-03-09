from middlewared.alert.base import Alert, AlertCategory, AlertClass, SimpleOneShotAlertClass, AlertLevel


class FailoverRebootAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Failover Event Caused System Reboot"
    text = (
        "%(fqdn)s had a failover event. The system was rebooted to ensure a "
        "proper failover occurred. The operating system successfully came "
        "back online at %(now)s."
    )

    async def create(self, args):
        return Alert(FailoverRebootAlertClass, {'fqdn': args['fqdn'], 'now': args['now']})

    async def delete(self, *args, **kwargs):
        return []


class FencedRebootAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Fenced Caused System Reboot"
    text = (
        '%(fqdn)s had a failover event. The system was rebooted because persistent '
        'SCSI reservations were lost and/or cleared. The operating system successfully '
        'came back online at %(now)s.'
    )

    async def create(self, args):
        return Alert(FencedRebootAlertClass, {'fqdn': args['fqdn'], 'now': args['now']})

    async def delete(self, *args, **kwargs):
        return []
