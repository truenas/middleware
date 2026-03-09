from dataclasses import dataclass

from middlewared.alert.base import OneShotAlertClass, AlertCategory, AlertClassConfig, AlertLevel


@dataclass(kw_only=True)
class UPSBatteryLowAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.UPS,
        level=AlertLevel.ALERT,
        title='UPS Battery LOW',
        text='UPS %(ups)s battery level low.%(body)s',
        deleted_automatically=False,
        keys=[],
    )

    ups: str
    body: str


@dataclass(kw_only=True)
class UPSOnlineAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.UPS,
        level=AlertLevel.INFO,
        title='UPS On Line Power',
        text='UPS %(ups)s is on line power.%(body)s',
        deleted_automatically=False,
        keys=[],
    )

    ups: str
    body: str


@dataclass(kw_only=True)
class UPSOnBatteryAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.UPS,
        level=AlertLevel.CRITICAL,
        title='UPS On Battery',
        text='UPS %(ups)s is on battery power.%(body)s',
        deleted_automatically=False,
        keys=[],
    )

    ups: str
    body: str


@dataclass(kw_only=True)
class UPSCommbadAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.UPS,
        level=AlertLevel.CRITICAL,
        title='UPS Communication Lost',
        text='Communication with UPS %(ups)s lost.%(body)s',
        deleted_automatically=False,
        keys=[],
    )

    ups: str
    body: str


@dataclass(kw_only=True)
class UPSCommokAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.UPS,
        level=AlertLevel.INFO,
        title='UPS Communication Established',
        text='Communication with UPS %(ups)s established.%(body)s',
        deleted_automatically=False,
        keys=[],
    )

    ups: str
    body: str


@dataclass(kw_only=True)
class UPSReplbattAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.UPS,
        level=AlertLevel.CRITICAL,
        title='UPS Battery Needs Replacement',
        text='UPS %(ups)s Battery needs replacement.%(body)s',
        deleted_automatically=False,
        keys=[],
    )

    ups: str
    body: str
