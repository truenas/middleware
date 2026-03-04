from middlewared.alert.base import AlertClass, AlertClassConfig, AlertCategory, AlertLevel, OneShotAlertClass


class KdumpNotReadyAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title='System Not Ready For Kdump',
        text='System is not ready for Kdump, please refer to kdump-config status.',
        deleted_automatically=False,
    )
