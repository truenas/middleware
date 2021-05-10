from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, OneShotAlertClass


class ApplicationsConfigurationFailedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.CRITICAL
    category = AlertCategory.APPLICATIONS
    title = 'Unable to Configure Applications'
    text = 'Failed to configure kubernetes cluster for Applications: %(error)s'

    async def create(self, args):
        return Alert(ApplicationsConfigurationFailedAlertClass, args)

    async def delete(self, alerts, query):
        return []


class ApplicationsStartFailedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.CRITICAL
    category = AlertCategory.APPLICATIONS
    title = 'Unable to Start Applications'
    text = 'Failed to start kubernetes cluster for Applications: %(error)s'

    async def create(self, args):
        return Alert(ApplicationsStartFailedAlertClass, args)

    async def delete(self, alerts, query):
        return []


class ChartReleaseUpdateAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.APPLICATIONS
    level = AlertLevel.INFO
    title = 'Application Update Available'
    text = 'An update is available for "%(name)s" application.'

    async def create(self, args):
        return Alert(ChartReleaseUpdateAlertClass, args, _key=args['id'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))
