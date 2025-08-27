import errno
from datetime import timedelta
from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils.directoryservices.constants import DSStatus
from middlewared.utils.directoryservices.health import (
    DSHealthObj, ADHealthError, IPAHealthError, KRB5HealthError, LDAPHealthError,
)
from middlewared.service_exception import CallError


class DirectoryServiceBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "DirectoryService Bind Is Not Healthy"
    text = "%(err)s."


class DirectoryServiceDnsUpdateAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "DirectoryService DNS Update Failed"
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


class DirectoryServiceDnsUpdateAlertSource(AlertSource):
    # The DNS updates are potentially going to happen every 7 days, but we check whether it's
    # needed more frequently. The reason for this is that users get a bit antsy if there's a
    # long-lived alert. The actual test itself (directoryservices.connection.refresh_dns) is not
    # expensive (a few datastore queries and reading a state file) and so once-per-hour isn't
    # going to generate excessive load.
    schedule = IntervalSchedule(timedelta(hours=1))
    run_on_backup_node = False

    async def check(self):
        if DSHealthObj.dstype is None:
            return

        try:
            # checks for enabled DS and whether DNS updates are enabled occur in this method
            await self.middleware.call('directoryservices.connection.refresh_dns')
        except RuntimeError as exc:
            # This most likely means somehow someone has cleared the kerberos realm without
            # disabling directory services. Most likely scenario is playing around with datastore
            # plugin or sqlite3 commands.
            self.middleware.logger.warning('Periodic DNS update failed due to misconfiguration.', exc_info=True)
            return Alert(DirectoryServiceDnsUpdateAlertClass, {'err', str(exc)}, key=None)
        except FileNotFoundError:
            # This happens if the system dataset is not mounted. We'll log an error but not
            # raise an alert because there are probably many other things hollering about the
            # broken sytsem dataset.
            self.middleware.logger.warning('Periodic DNS update failed due to broken system dataset.', exc_info=True)
        except CallError as exc:
            self.middleware.logger.warning('Periodic DNS update failed.', exc_info=True)

            if exc.errno == errno.ENOKEY:
                # No kerberos ticket
                errmsg = (
                    'Unable to perform DNS update because no kerberos ticket is available. '
                    'See the DirectoryServiceBindAlert for more information. This alert will clear itself during the '
                    'next check after directory services are healthy again.'
                )
            else:
                errmsg = exc.errmsg

            return Alert(DirectoryServiceDnsUpdateAlertClass, {'err', errmsg}, key=None)
        except Exception as exc:
            # If needed we can enhance this in the future to parse CallError
            self.middleware.logger.warning('Periodic DNS update failed.', exc_info=True)
            return Alert(DirectoryServiceDnsUpdateAlertClass, {'err', str(exc)}, key=None)
