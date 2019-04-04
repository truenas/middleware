from datetime import timedelta
import os
import logging
from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource
from middlewared.alert.schedule import IntervalSchedule

log = logging.getLogger("activedirectory_check_alertmod")

class ActiveDirectoryDomainHealthAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "Problem detected in Active Directory Domain"

    schedule = IntervalSchedule(timedelta(hours=24))

    def check_sync(self):
        ad = self.middleware.call_sync("activedirectory.config")
        if not ad['enable']:
            return

        try:
            self.middleware.call_sync("activedirectory.validate_domain")
        except Exception as e:
            return Alert(f"AD domain validation failed with error: {e}")


class ActiveDirectoryDomainBindAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "Active Directory Status Check Failed"

    schedule = IntervalSchedule(timedelta(minutes=10))

    def check_sync(self):
        ad = self.middleware.call_sync("activedirectory.config")
        if not ad['enable']:
            return

        if not self.middleware.call_sync("activedirectory.started"):
            return Alert("Attempt to connect to netlogon share for domain failed")