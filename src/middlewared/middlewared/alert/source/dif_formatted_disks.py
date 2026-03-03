from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, SimpleOneShotAlertClass


class DifFormattedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    keys = []
    title = 'Disk(s) Are Formatted With Data Integrity Feature (DIF).'
    text = 'Disk(s): %s are formatted with Data Integrity Feature (DIF) which is unsupported.'

    def key(self, args):
        return None
