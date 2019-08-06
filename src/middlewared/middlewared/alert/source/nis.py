from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


class NISBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "NIS Bind Is Not Healthy"
    text = "NIS bind health check failed: %(niserr)s."


class NISBindAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=30))

    async def check(self):
        if (await self.middleware.call('nis.get_state')) == 'DISABLED':
            return

        smbhamode = await self.middleware.call('smb.get_smb_ha_mode')
        if smbhamode != 'STANDALONE' and (await self.middleware.call('failover.status')) != 'MASTER':
            return

        try:
            await self.middleware.call("nis.started")
        except Exception as e:
            return Alert(
                NISBindAlertClass,
                {'niserr': str(e)},
                key=None
            )
