from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, OneShotAlertClass


class FailuresInAppMigrationAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.APPLICATIONS
    level = AlertLevel.ERROR
    title = 'App(s) failed to migrate'
    text = 'App(s) failed to migrate, please check /var/log/app_migrations.log for more details.'

    async def create(self, args):
        return Alert(FailuresInAppMigrationAlertClass, args)

    async def delete(self, alerts, query):
        return []


class ApplicationsConfigurationFailedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.CRITICAL
    category = AlertCategory.APPLICATIONS
    title = 'Unable to Configure Applications'
    text = 'Failed to configure docker for Applications: %(error)s'

    async def create(self, args):
        return Alert(ApplicationsConfigurationFailedAlertClass, args)

    async def delete(self, alerts, query):
        return []


class ApplicationsStartFailedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.CRITICAL
    category = AlertCategory.APPLICATIONS
    title = 'Unable to Start Applications'
    text = 'Failed to start docker for Applications: %(error)s'

    async def create(self, args):
        return Alert(ApplicationsStartFailedAlertClass, args)

    async def delete(self, alerts, query):
        return []


class AppUpdateAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.APPLICATIONS
    level = AlertLevel.INFO
    title = 'Application Update Available'
    text = 'An update is available for "%(name)s" application.'

    async def create(self, args):
        return Alert(AppUpdateAlertClass, args, _key=args['name'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != query,
            alerts
        ))
