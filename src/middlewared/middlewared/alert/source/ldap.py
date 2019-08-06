from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


class LDAPBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "LDAP Bind Is Not Healthy"
    text = "Attempt to connect to root DSE failed: %(ldaperr)s."


class LDAPBindAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=30))

    async def check(self):
        if (await self.middleware.call('ldap.get_state')) == 'DISABLED':
            return

        smbhamode = await self.middleware.call('smb.get_smb_ha_mode')
        if smbhamode != 'STANDALONE' and (await self.middleware.call('failover.status')) != 'MASTER':
            return

        try:
            await self.middleware.call("ldap.started")
        except Exception as e:
            return Alert(
                LDAPBindAlertClass,
                {'ldaperr': str(e)},
                key=None
            )
