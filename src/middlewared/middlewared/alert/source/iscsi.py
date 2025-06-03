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


class ISCSIAuthSecretInvalidCharAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = 'iSCSI Authorized Access has an invalid character'
    text = 'The iSCSI Authorized Access with Group ID %(tag)d and %(userfield)s %(user)r has a %(field)s containing the invalid character: %(char)r.'


class ISCSIAuthSecretWhitespaceAlertClass(AlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = 'iSCSI Authorized Access has leading or trailing whitespace'
    text = 'The iSCSI Authorized Access with Group ID %(tag)d and %(userfield)s %(user)r has a %(field)s containing leading or trailing whitespace.'


class ISCSIAuthSecretAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=24))
    run_on_backup_node = False
    INVALID_CHARS = '#'

    async def check(self):
        alerts = []

        private_to_public = {
            'user': 'User',
            'secret': 'Secret',
            'peeruser': 'Peer User',
            'peersecret': 'Peer Secret'
        }

        auths = await self.middleware.call('iscsi.auth.query')
        for auth in auths:
            for userfield, secretfield in [('user', 'secret'),
                                           ('peeruser', 'peersecret')]:
                if auth[userfield] and auth[secretfield]:
                    for char in self.INVALID_CHARS:
                        if char in auth[secretfield]:
                            alerts.append(Alert(ISCSIAuthSecretInvalidCharAlertClass,
                                                {'field': private_to_public[secretfield],
                                                 'tag': auth['tag'],
                                                 'userfield': private_to_public[userfield],
                                                 'user': auth[userfield],
                                                 'char': char
                                                 }, key=auth['id']))
                    if auth[secretfield] != auth[secretfield].strip():
                        alerts.append(Alert(ISCSIAuthSecretWhitespaceAlertClass,
                                            {'field': private_to_public[secretfield],
                                             'tag': auth['tag'],
                                             'userfield': private_to_public[userfield],
                                             'user': auth[userfield],
                                             }, key=auth['id']))

        return alerts
