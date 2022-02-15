from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource

TITLE = 'Disks Missing On '
TEXT = 'Disks with serial %(serial)s present on '


class DisksAreNotPresentOnStandbyNodeAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = TITLE + 'Standby Storage Controller'
    text = TEXT + 'active storage controller but missing on standby storage controller.'
    products = ('SCALE_ENTERPRISE',)


class DisksAreNotPresentOnActiveNodeAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = TITLE + 'Active Storage Controller'
    text = TEXT + 'standby storage controller but missing on active storage controller.'
    products = ('SCALE_ENTERPRISE',)


class FailoverDisksAlertSource(AlertSource):
    products = ('SCALE_ENTERPRISE',)
    failover_related = True
    run_on_backup_node = False

    async def check(self):
        licensed = await self.middleware.call('failover.licensed')
        if licensed and (md := await self.middleware.call('failover.mismatch_disks')):
            if md['missing_remote']:
                return [Alert(
                    DisksAreNotPresentOnStandbyNodeAlertClass, {'serials': ', '.join(md['missing_remote'])}
                )]
            if md['missing_remote']:
                return [Alert(
                    DisksAreNotPresentOnActiveNodeAlertClass, {'serials': ', '.join(md['missing_remote'])}
                )]
        return []
