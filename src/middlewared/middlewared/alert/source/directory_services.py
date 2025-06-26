from datetime import timedelta
from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils.directoryservices.constants import DSStatus
from middlewared.utils.directoryservices.health import (
    DSHealthObj, ADHealthError, IPAHealthError, KRB5HealthError, LDAPHealthError,
)


class DirectoryServiceBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "DirectoryService Bind Is Not Healthy"
    text = "%(err)s."


class DirectoryServiceDomainBindAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=10))
    run_on_backup_node = False

    async def check(self):
        if DSHealthObj.dstype is None:
            return

        if DSHealthObj.status in (DSStatus.JOINING, DSStatus.LEAVING):
            # Some op is in progress, don't interfere
            return

        try:
            await self.middleware.call('directoryservices.health.check')
        except (KRB5HealthError, ADHealthError, LDAPHealthError, IPAHealthError):
            # this is potentially recoverable
            try:
                await self.middleware.call('directoryservices.health.recover')
            except Exception as e:
                # Recovery failed, generate an alert
                return Alert(DirectoryServiceBindAlertClass, {'err': str(e)}, key=None)

        except Exception:
            # We shouldn't be raising other sorts of errors
            self.logger.error("Unexpected error while performing health check.", exc_info=True)
