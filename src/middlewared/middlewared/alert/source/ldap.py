from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.plugins.directoryservices import DSStatus, DSType
from middlewared.utils.directoryservices.health import DSHealthObj


class LDAPBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "LDAP Bind Is Not Healthy"
    text = "%(ldaperr)s."


class LDAPBindAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=10))
    run_on_backup_node = False

    async def check(self):
        if DSHealthObj.dstype is not DSType.LDAP: 
            return

        try:
            await self.middleware.call('directoryservices.health.check')
        except (KRB5HealthError, LDAPHealthError):
            # this is potentially recoverable
            try:
                await self.middleware.call('directoryservices.health.recover')
            except Exception as e:
                # Recovery failed, generate an alert
                return Alert(
                    LDAPBindAlertClass,
                    {'ldaperr': str(e)},
                    key=None
                )
        except Exception:
            # We shouldn't be raising other sorts of errors
            self.logger.error("Unexpected error while performing health check.", exc_info=True)
