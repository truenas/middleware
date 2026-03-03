from middlewared.alert.base import AlertCategory, AlertClass, AlertClassConfig, AlertLevel, OneShotAlertClass


class FCHardwareAddedAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title='Fibre Channel HBAs added.',
        text=(
            'Fibre Channel HBAs added.  '
            'Fibre Channel switches may require reconfiguration.'
        ),
        deleted_automatically=False,
    )


class FCHardwareReplacedAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.CRITICAL,
        title='Fibre Channel HBAs replaced.',
        text=(
            'Fibre Channel HBAs replaced.  '
            'Target/WWPN mapping may have changed.  '
            'Fibre Channel switches may require reconfiguration.'
        ),
        deleted_automatically=False,
    )
