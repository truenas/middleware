from middlewared.alert.base import Alert, AlertClass, AlertCategory, OneShotAlertClass, AlertLevel


class DifFormattedAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = 'Disk(s) Are Formatted With Data Integrity Feature (DIF).'
    text = 'Disk(s): %s are formatted with Data Integrity Feature (DIF) which is unsupported.'

    async def create(self, disks):
        return Alert(DifFormattedAlertClass, ', '.join(disks), key=None)

    async def delete(self, alerts, query):
        return []
