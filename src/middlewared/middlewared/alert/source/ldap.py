from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils.directoryservices.constants import DSType
from middlewared.plugins.directoryservices_.all import get_enabled_ds


class LDAPBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "LDAP Bind Is Not Healthy"
    text = "LDAP health check failed: %(ldaperr)s."


class LDAPBindAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=10))
    run_on_backup_node = False

    async def check(self):
        ds_obj = await self.middleware.run_in_thread(get_enabled_ds)
        if ds_obj is None or ds_obj.ds_type is not DSType.LDAP:
            return

        try:
            await self.middleware.run_in_thread(ds_obj.health_check)
        except Exception as e:
            return Alert(
                LDAPBindAlertClass,
                {'ldaperr': str(e)},
                key=None
            )
