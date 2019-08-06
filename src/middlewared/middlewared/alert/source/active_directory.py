from datetime import timedelta
import logging
from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource, SimpleOneShotAlertClass
from middlewared.alert.schedule import CrontabSchedule, IntervalSchedule

log = logging.getLogger("activedirectory_check_alertmod")


class ActiveDirectoryDomainBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "Active Directory Bind Is Not Healthy"
    text = "Attempt to connect to netlogon share failed with error: %(wberr)s."


class ActiveDirectoryDomainHealthAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "Active Directory Domain Validation Failed"
    text = "Domain validation failed with error: %(verrs)s."


class ActiveDirectoryDomainOfflineAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "Domain Offline"
    text = "Active Directory Domain \"%(domain)s\" is Offline."


class ActiveDirectoryDomainHealthAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=1)

    async def check(self):
        if await self.middleware.call('activedirectory.get_state') == 'DISABLED':
            return

        smbhamode = await self.middleware.call('smb.get_smb_ha_mode')
        if smbhamode != 'STANDALONE' and (await self.middleware.call('failover.status')) != 'MASTER':
            return

        try:
            await self.middleware.call("activedirectory.validate_domain")
        except Exception as e:
            return Alert(
                ActiveDirectoryDomainHealthAlertClass,
                {'verrs': str(e)},
                key=None
            )


class ActiveDirectoryDomainBindAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=10))

    async def check(self):
        if (await self.middleware.call('activedirectory.get_state')) == 'DISABLED':
            return

        smbhamode = await self.middleware.call('smb.get_smb_ha_mode')
        if smbhamode != 'STANDALONE' and (await self.middleware.call('failover.status')) != 'MASTER':
            return

        try:
            await self.middleware.call("activedirectory.started")
        except Exception as e:
            return Alert(
                ActiveDirectoryDomainBindAlertClass,
                {'wberr': str(e)},
                key=None
            )
