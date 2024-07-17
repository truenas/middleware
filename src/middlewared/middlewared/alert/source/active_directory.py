from datetime import timedelta
import errno
import logging
from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import CrontabSchedule, IntervalSchedule
from middlewared.plugins.directoryservices import DSStatus
from middlewared.service_exception import CallError
from middlewared.utils.directoryservices.constants import DSType
from middlewared.utils.directoryservices.health import DSHealthObj, ADHealthError, KRB5HealthError

log = logging.getLogger("activedirectory_check_alertmod")


class ActiveDirectoryDomainBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "Active Directory Bind Is Not Healthy"
    text = "%(wberr)s."


class ActiveDirectoryDomainHealthAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "Active Directory Domain Validation Failed"
    text = "Domain validation failed with error: %(verrs)s"


class ActiveDirectoryDomainHealthAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)
    run_on_backup_node = False

    async def check(self):
        if DSHealthObj.dstype is not DSType.AD:
            return

        conf = await self.middleware.call("activedirectory.config")

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
        if DSHealthObj.dstype is not DSType.AD:
            return

        if DSHealthObj.status in (DSStatus.JOINING, DSStatus.LEAVING):
            return

        try:
            await self.middleware.call('directoryservices.health.check')
        except (KRB5HealthError, ADHealthError):
            # this is potentially recoverable
            try:
                await self.middleware.call('directoryservices.health.recover')
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
