from dataclasses import dataclass

from middlewared.alert.base import AlertClassConfig, AlertCategory, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class ApplicationsConfigurationFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.APPLICATIONS,
        level=AlertLevel.CRITICAL,
        title='Unable to Configure Applications',
        text='Failed to configure docker for Applications: %(error)s',
        deleted_automatically=False,
        keys=[],
    )

    error: str


@dataclass(kw_only=True)
class ApplicationsStartFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.APPLICATIONS,
        level=AlertLevel.CRITICAL,
        title='Unable to Start Applications',
        text='Failed to start docker for Applications: %(error)s',
        deleted_automatically=False,
        keys=[],
    )

    error: str


@dataclass(kw_only=True)
class AppUpdateAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.APPLICATIONS,
        level=AlertLevel.INFO,
        title='Application Update Available',
        text='Updates are available for %(count)d application%(plural)s: %(apps)s',
        deleted_automatically=False,
        keys=[],
    )

    count: int
    plural: str
    apps: str
