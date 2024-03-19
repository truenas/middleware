from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource
from middlewared.alert.schedule import IntervalSchedule


class ISCSIPortalIPAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = 'IP Addresses Bound to an iSCSI Portal Were Not Found'
    text = 'These IP addresses are bound to an iSCSI Portal but not found: %s.'


class ISCSIPortalIPAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=60))

    async def check(self):
        try:
            started = await self.middleware.call('service.started', 'iscsitarget')
        except Exception:
            # during upgrade this crashed in `pystemd.dbusexc.DBusTimeoutError: [err -110]: b'Connection timed out'`
            # so don't pollute the webUI with tracebacks
            return
        else:
            if not started:
                return

        in_use_ips = {i['address'] for i in await self.middleware.call('interface.ip_in_use', {'any': True})}
        portals = {p['id']: p for p in await self.middleware.call('iscsi.portal.query')}
        ips = set()
        for target in await self.middleware.call('iscsi.target.query'):
            for group in target['groups']:
                ips.update(
                    map(
                        lambda ip: ip['ip'],
                        filter(lambda a: a['ip'] not in in_use_ips, portals[group['portal']]['listen'])
                    )
                )

        if ips and await self.middleware.call('iscsi.global.alua_enabled'):
            # When ALUA is enabled on HA, the STANDBY node will report the
            # virtual IPs as missing.  Remove them if the corresponding
            # underlying IP is in use.
            choices = await self.middleware.call('iscsi.portal.listen_ip_choices')
            node = await self.middleware.call('failover.node')
            if node in ['A', 'B']:
                index = ['A', 'B'].index(node)
                vips = {k: v.split('/')[index] for k, v in choices.items() if v.find('/') != -1}
                ok = {ip for ip in ips if ip in vips and vips[ip] in in_use_ips}
                ips -= ok

        if ips:
            return Alert(ISCSIPortalIPAlertClass, ', '.join(ips))
