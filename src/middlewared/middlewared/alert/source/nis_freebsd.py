from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, Alert, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.plugins.directoryservices import DSStatus


class NISBindAlertClass(AlertClass):
    category = AlertCategory.DIRECTORY_SERVICE
    level = AlertLevel.WARNING
    title = "NIS Bind Is Not Healthy"
    text = "NIS bind health check failed: %(niserr)s."


class NISBindAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(minutes=10))
    run_on_backup_node = False

    async def check(self):
        if (await self.middleware.call('nis.get_state')) == 'DISABLED':
            return

        try:
            await self.middleware.call("nis.started")
        except Exception as e:
            await self.middleware.call('nis.set_state', DSStatus['FAULTED'])
            return Alert(
                NISBindAlertClass,
                {'niserr': str(e)},
                key=None
            )
