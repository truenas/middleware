from middlewared.alert.base import Alert, AlertClass, AlertCategory, AlertLevel, OneShotAlertClass


class TruecommandConnectionDisabledAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = 'TrueCommand API Key Disabled by iX Portal'
    text = 'TrueCommand API Key has been disabled by iX Portal: %(error)s'

    async def create(self, args):
        return Alert(TruecommandConnectionDisabledAlertClass, args)

    async def delete(self, alerts, query):
        return []


class TruecommandConnectionPendingAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.SYSTEM
    level = AlertLevel.INFO
    title = 'Pending Confirmation From iX Portal for TrueCommand API Key'
    text = 'Confirmation is pending for TrueCommand API Key from iX Portal: %(error)s'

    async def create(self, args):
        return Alert(TruecommandConnectionPendingAlertClass, args)

    async def delete(self, alerts, query):
        return []


class TruecommandConnectionHealthAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.SYSTEM
    level = AlertLevel.CRITICAL
    title = 'TrueCommand Service Failed Scheduled Health Check'
    text = 'TrueCommand service failed scheduled health check, please confirm NAS ' \
           'has been registered with TrueCommand and TrueCommand is able to access NAS.'

    async def create(self, args):
        return Alert(TruecommandConnectionHealthAlertClass, args)

    async def delete(self, alerts, query):
        return []
