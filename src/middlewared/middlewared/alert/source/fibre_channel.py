from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass


class FCHardwareAddedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.WARNING
    title = 'Fibre Channel HBAs added.'
    text = (
        'Fibre Channel HBAs added.  '
        'Fibre Channel switches may require reconfiguration.'
    )

    deleted_automatically = False


class FCHardwareReplacedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SHARING
    level = AlertLevel.CRITICAL
    title = 'Fibre Channel HBAs replaced.'
    text = (
        'Fibre Channel HBAs replaced.  '
        'Target/WWPN mapping may have changed.  '
        'Fibre Channel switches may require reconfiguration.'
    )

    deleted_automatically = False
