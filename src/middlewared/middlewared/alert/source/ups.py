from middlewared.alert.base import OneShotAlertClass, AlertClass, AlertCategory, AlertClassConfig, AlertLevel


class UPSBatteryLowAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.UPS,
        level=AlertLevel.ALERT,
        title='UPS Battery LOW',
        text='UPS %(ups)s battery level low.%(body)s',
        deleted_automatically=False,
        keys=[],
    )


class UPSOnlineAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.UPS,
        level=AlertLevel.INFO,
        title='UPS On Line Power',
        text='UPS %(ups)s is on line power.%(body)s',
        deleted_automatically=False,
        keys=[],
    )


class UPSOnBatteryAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.UPS,
        level=AlertLevel.CRITICAL,
        title='UPS On Battery',
        text='UPS %(ups)s is on battery power.%(body)s',
        deleted_automatically=False,
        keys=[],
    )


class UPSCommbadAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.UPS,
        level=AlertLevel.CRITICAL,
        title='UPS Communication Lost',
        text='Communication with UPS %(ups)s lost.%(body)s',
        deleted_automatically=False,
        keys=[],
    )


class UPSCommokAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.UPS,
        level=AlertLevel.INFO,
        title='UPS Communication Established',
        text='Communication with UPS %(ups)s established.%(body)s',
        deleted_automatically=False,
        keys=[],
    )


class UPSReplbattAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.UPS,
        level=AlertLevel.CRITICAL,
        title='UPS Battery Needs Replacement',
        text='UPS %(ups)s Battery needs replacement.%(body)s',
        deleted_automatically=False,
        keys=[],
    )
