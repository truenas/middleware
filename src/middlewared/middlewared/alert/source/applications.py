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
    text = 'Updates are available for %(count)d application%(plural)s: %(apps)s'

    async def create(self, args):
        # Format the text based on number of apps
        count = args.get('count', len(args.get('apps', [])))
        apps = args.get('apps', [])
        args['plural'] = 's' if count != 1 else ''
        args['apps'] = ', '.join(apps)
        return Alert(AppUpdateAlertClass, args)

    async def delete(self, alerts, query):
        return []
