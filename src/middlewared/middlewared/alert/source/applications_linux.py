from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, OneShotAlertClass


class ApplicationsStartFailedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.CRITICAL
    category = AlertCategory.APPLICATIONS
    title = 'Unable to Start Applications'
    text = 'Failed to start kubernetes cluster for Applications'

    async def create(self, args):
        return Alert(ApplicationsStartFailedAlertClass, args)

    async def delete(self, alerts, query):
        return []
