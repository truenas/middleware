from datetime import timedelta
import os
import logging
from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

log = logging.getLogger("activedirectory_check_alertmod")

class ActiveDirectoryDomainBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "ActiveDirectory Bind Is Not Healthy"
    text = "Attempt to connect to netlogon share failed with error: %(wberr)s."


class ActiveDirectoryDomainHealthAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "ActiveDirectory Domain Validation Failed"
    text = "Domain validation failed with error: %(verrs)s."


class ActiveDirectoryDomainHealthAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(timedelta(hours=24))

    def check_sync(self):
        if self.middleware.call_sync('activedirectory.get_state') == 'DISABLED':
            return

        try:
            self.middleware.call_sync("activedirectory.validate_domain")
        except Exception as e:
            return Alert(
                ActiveDirectoryDomainHealthAlertClass,
                {'verrs': str(e)}
            )


class ActiveDirectoryDomainBindAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(timedelta(minutes=10))

    async def check(self):
        if (await self.middleware.call('activedirectory.get_state')) == 'DISABLED':
            return

        try:
            await self.middleware.call("activedirectory.started")
        except Exception as e:
            return Alert(
                ActiveDirectoryDomainBindAlertClass,
                {'wberr': str(e)},
                key=None
            )
