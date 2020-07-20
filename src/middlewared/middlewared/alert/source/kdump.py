from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, SimpleOneShotAlertClass


class KdumpNotReadyAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.WARNING
    category = AlertCategory.SYSTEM
    title = 'System Not Ready For Kdump'
    text = 'System is not ready for Kdump, please refer to kdump-config status.'
