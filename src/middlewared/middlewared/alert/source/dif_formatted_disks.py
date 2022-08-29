from middlewared.alert.base import Alert, AlertSource, AlertClass, AlertCategory, AlertLevel
from middlewared.alert.schedule import CrontabSchedule


class DifFormattedAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = 'Disk(s) Are Formatted With Data Integrity Feature (DIF).'
    text = 'Disk(s): %s are formatted with Data Integrity Feature (DIF) which is unsupported.'


class DifFormattedAlertSource(AlertSource):
    schedule = CrontabSchedule(hour=0)  # every 24 hours
    run_on_backup_node = False

    async def check(self):
        dif = []
        for disk, info in filter(lambda x: x[1]['dif'], (await self.middleware.call('device.get_disks')).items()):
            dif.append(disk)

        if dif:
            return Alert(DifFormattedAlertClass, ', '.join(dif))
