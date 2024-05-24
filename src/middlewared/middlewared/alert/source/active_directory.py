from datetime import timedelta
import logging
from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import CrontabSchedule, IntervalSchedule
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.health import (
    KRB5HealthError, ADHealthError,
)
from middlewared.plugins.directoryservices_.all import get_enabled_ds
from middlewared.service_exception import CallError

log = logging.getLogger("activedirectory_check_alertmod")


class ActiveDirectoryDomainBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "Active Directory Bind Is Not Healthy"
    text = "Attempt to connect to domain controller failed: %(wberr)s."


class ActiveDirectoryDomainHealthAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "Active Directory Domain Validation Failed"
    text = "Domain validation failed with error: %(verrs)s"


class ActiveDirectoryDomainHealthAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)
    run_on_backup_node = False

    async def check(self):
        ds_obj = await self.middleware.run_in_thread(get_enabled_ds)
        if ds_obj is None or ds_obj.ds_type is not DSType.AD:
            return

        conf = ds_obj.config
        try:
            await self.middleware.call("activedirectory.check_nameservers", conf["domainname"], conf["site"])
        except CallError as e:
            return Alert(
                ActiveDirectoryDomainHealthAlertClass,
                {'verrs': e.errmsg},
                key=None
            )


class ActiveDirectoryDomainBindAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=10))
    run_on_backup_node = False

    async def check(self):
        ds_obj = await self.middleware.run_in_thread(get_enabled_ds)
        if ds_obj is None or ds_obj.ds_type is not DSType.AD:
            return

        try:
            await self.middleware.run_in_thread(ds_obj.health_check)
        except (KRB5HealthError, ADHealthError):
            # this is potentially recoverable
            try:
                await self.middleware.call('directoryservices.recover')
            except Exception as e:
                # Recovery failed, generate an alert
                return Alert(
                    ActiveDirectoryDomainBindAlertClass,
                    {'wberr': str(e)},
                    key=None
                )
        except Exception:
            # We shouldn't be raising other sorts of errors
            self.logger.error("Unexpected error while performing health check.", exc_info=True)
