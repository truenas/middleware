from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, SimpleOneShotAlertClass


class FailuresInAppMigrationAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False
    keys = []

    category = AlertCategory.APPLICATIONS
    level = AlertLevel.ERROR
    title = 'App(s) failed to migrate'
    text = 'App(s) failed to migrate, please check /var/log/app_migrations.log for more details.'


class ApplicationsConfigurationFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False
    keys = []
    level = AlertLevel.CRITICAL
    category = AlertCategory.APPLICATIONS
    title = 'Unable to Configure Applications'
    text = 'Failed to configure docker for Applications: %(error)s'


class ApplicationsStartFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False
    keys = []
    level = AlertLevel.CRITICAL
    category = AlertCategory.APPLICATIONS
    title = 'Unable to Start Applications'
    text = 'Failed to start docker for Applications: %(error)s'


class AppUpdateAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False
    keys = []

    category = AlertCategory.APPLICATIONS
    level = AlertLevel.INFO
    title = 'Application Update Available'
    text = 'Updates are available for %(count)d application%(plural)s: %(apps)s'
