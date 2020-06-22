from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource, OneShotAlertClass
from middlewared.alert.schedule import IntervalSchedule


class ISCSIPortalIPAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = 'IP Addresses Bound to an iSCSI Portal Were Not Found'
    text = 'These IP addresses are bound to an iSCSI Portal but not found: %s.'


class ISCSIPortalIPAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=60))

    async def check(self):
        if not await self.middleware.call('service.started', 'iscsitarget'):
            return

        in_use_ips = {i['address'] for i in await self.middleware.call('interface.ip_in_use', {'any': True})}
        portals = {p['id']: p for p in await self.middleware.call('iscsi.portal.query')}
        ips = []
        for target in await self.middleware.call('iscsi.target.query'):
            for group in target['groups']:
                ips.extend(
                    map(
                        lambda ip: ip['ip'],
                        filter(lambda a: a['ip'] not in in_use_ips, portals[group['portal']]['listen'])
                    )
                )

        if ips:
            return Alert(ISCSIPortalIPAlertClass, ', '.join(ips))


class ISCSIExtentLockedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = 'iSCSI Extent Locked'
    text = 'iSCSI "%(name)s" extent is using a locked resource. Please disable the extent.'

    async def create(self, args):
        return Alert(ISCSIExtentLockedAlertClass, args, key=args['id'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))
