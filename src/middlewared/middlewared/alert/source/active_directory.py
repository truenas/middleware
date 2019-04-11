from datetime import timedelta
import os
import logging
from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

log = logging.getLogger("activedirectory_check_alertmod")

class ActiveDirectoryBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "ActiveDirectory Bind is Not Healthy"
    text = "Attempt to connect to netlogon share failed with error: %(wberr)s"


class ActiveDirectoryDomainHealthAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "ActiveDirectory Domain Validation Failed"
    text = "Domain validation failed with error: %(verrs)s"


class ActiveDirectoryDomainHealthAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(timedelta(hours=24))

    def check_sync(self):
        ad = self.middleware.call_sync("activedirectory.config")
        if not ad['enable']:
            return

        try:
            self.middleware.call_sync("activedirectory.validate_domain")
        except Exception as e:
            return Alert(
                ActiveDirectoryDomainHealthAlertClass,
                {'verrs': e}
            )


class ActiveDirectoryDomainBindAlertSource(ThreadedAlertSource):
    schedule = IntervalSchedule(timedelta(minutes=10))

    def check_sync(self):
        ad = self.middleware.call_sync("activedirectory.config")
        if not ad['enable']:
            return

        try:
            self.middleware.call_sync("activedirectory.started")
        except Exception as e:
            return Alert(
                ActiveDirectoryBindAlertClass,
                {'wberr': f'{e}'}
            )
