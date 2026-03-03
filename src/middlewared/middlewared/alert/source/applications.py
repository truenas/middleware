from middlewared.alert.base import AlertClass, AlertClassConfig, AlertCategory, AlertLevel, OneShotAlertClass


class ApplicationsConfigurationFailedAlertClass(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.APPLICATIONS,
        level=AlertLevel.CRITICAL,
        title='Unable to Configure Applications',
        text='Failed to configure docker for Applications: %(error)s',
        deleted_automatically=False,
        keys=[],
    )


class ApplicationsStartFailedAlertClass(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.APPLICATIONS,
        level=AlertLevel.CRITICAL,
        title='Unable to Start Applications',
        text='Failed to start docker for Applications: %(error)s',
        deleted_automatically=False,
        keys=[],
    )


class AppUpdateAlertClass(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.APPLICATIONS,
        level=AlertLevel.INFO,
        title='Application Update Available',
        text='Updates are available for %(count)d application%(plural)s: %(apps)s',
        deleted_automatically=False,
        keys=[],
    )
