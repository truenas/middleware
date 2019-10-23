from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.plugins.directoryservices import DSStatus


class LDAPBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "LDAP Bind Is Not Healthy"
    text = "Attempt to connect to root DSE failed: %(ldaperr)s."


class LDAPBindAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=10))
    run_on_backup_node = False

    async def check(self):
        if (await self.middleware.call('ldap.get_state')) == 'DISABLED':
            return

        try:
            await self.middleware.call("ldap.started")
        except Exception as e:
            await self.middleware.call('ldap.set_state', DSStatus['FAULTED'])
            return Alert(
                LDAPBindAlertClass,
                {'ldaperr': str(e)},
                key=None
            )
