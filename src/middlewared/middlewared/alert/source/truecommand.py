from middlewared.alert.base import Alert, AlertClass, AlertCategory, AlertLevel, OneShotAlertClass


class TruecommandConnectionDisabledAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = 'Truecommand API Key Disabled by iX Portal'
    text = 'Truecommand API Key has been disabled by iX Portal: %(error)s'

    async def create(self, args):
        return Alert(TruecommandConnectionDisabledAlertClass, args)

    async def delete(self, alerts, query):
        return []


class TruecommandConnectionPendingAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.SYSTEM
    level = AlertLevel.INFO
    title = 'Pending Confirmation From iX Portal for Truecommand API Key'
    text = 'Confirmation is pending for Truecommand API Key from iX Portal: %(error)s'

    async def create(self, args):
        return Alert(TruecommandConnectionPendingAlertClass, args)

    async def delete(self, alerts, query):
        return []


class TruecommandConnectionHealthAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = 'Truecommand Service Failed Scheduled Health Check'
    text = 'Truecommand service failed scheduled health check, connecting with iX Portal to get details'

    async def create(self, args):
        return Alert(TruecommandConnectionHealthAlertClass, args)

    async def delete(self, alerts, query):
        return []
