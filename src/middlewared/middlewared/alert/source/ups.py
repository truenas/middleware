from middlewared.alert.base import OneShotAlertClass, AlertClass, AlertCategory, AlertLevel


class UPSBatteryLowAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.UPS
    level = AlertLevel.ALERT
    title = 'UPS Battery LOW'
    text = 'UPS %(ups)s battery level low.%(body)s'

    deleted_automatically = False
    keys = []


class UPSOnlineAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.UPS
    level = AlertLevel.INFO
    title = 'UPS On Line Power'
    text = 'UPS %(ups)s is on line power.%(body)s'

    deleted_automatically = False
    keys = []


class UPSOnBatteryAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.UPS
    level = AlertLevel.CRITICAL
    title = 'UPS On Battery'
    text = 'UPS %(ups)s is on battery power.%(body)s'

    deleted_automatically = False
    keys = []


class UPSCommbadAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.UPS
    level = AlertLevel.CRITICAL
    title = 'UPS Communication Lost'
    text = 'Communication with UPS %(ups)s lost.%(body)s'

    deleted_automatically = False
    keys = []


class UPSCommokAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.UPS
    level = AlertLevel.INFO
    title = 'UPS Communication Established'
    text = 'Communication with UPS %(ups)s established.%(body)s'

    deleted_automatically = False
    keys = []


class UPSReplbattAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.UPS
    level = AlertLevel.CRITICAL
    title = 'UPS Battery Needs Replacement'
    text = 'UPS %(ups)s Battery needs replacement.%(body)s'

    deleted_automatically = False
    keys = []
