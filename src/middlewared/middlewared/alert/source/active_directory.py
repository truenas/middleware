from datetime import timedelta
import logging
from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import CrontabSchedule, IntervalSchedule
from middlewared.plugins.directoryservices import DSStatus
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
        if await self.middleware.call('activedirectory.get_state') == 'DISABLED':
            return

        try:
            await self.middleware.call("activedirectory.validate_domain")
        except Exception as e:
            await self.middleware.call("activedirectory.set_state", DSStatus['FAULTED'].name)
            return Alert(
                ActiveDirectoryDomainHealthAlertClass,
                {'verrs': str(e)},
                key=None
            )

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
        if not (await self.middleware.call('activedirectory.config'))['enable']:
            return

        try:
            await self.middleware.call("activedirectory.started")
        except CallError as e:
            if e.errno == errno.EINVAL:
                new_status = DSStatus.DISABLED
                # ValidationErrors text is crammed into e.extra
                errmsg = f'Configuration validation failed: {e.extra}'
            else:
                new_status = DSStatus.FAULTED
                errmsg = str(e.errmsg)

            await self.middleware.call("activedirectory.set_state", new_status.name)
            return Alert(
                ActiveDirectoryDomainBindAlertClass,
                {'wberr': errmsg},
                key=None
            )
        except Exception as e:
            await self.middleware.call("activedirectory.set_state", DSStatus['FAULTED'].name)
            return Alert(
                ActiveDirectoryDomainBindAlertClass,
                {'wberr': str(e)},
                key=None
            )
