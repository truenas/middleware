from middlewared.alert.base import AlertClass, AlertClassConfig, AlertCategory, AlertLevel, OneShotAlertClass


class DifFormattedAlertClass(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.CRITICAL,
        title='Disk(s) Are Formatted With Data Integrity Feature (DIF).',
        text='Disk(s): %s are formatted with Data Integrity Feature (DIF) which is unsupported.',
        keys=[],
    )

    @classmethod
    def key(cls, args):
        return None
