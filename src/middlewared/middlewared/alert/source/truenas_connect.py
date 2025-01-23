from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, OneShotAlertClass


class TNCHeartbeatConnectionFailureAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.ERROR
    category = AlertCategory.TRUENAS_CONNECT
    title = 'Unable to connect to TrueNAS Connect Heartbeat Service'
    text = 'Failed to connect to TrueNAS Connect Heartbeat Service in the last 48 hours'

    async def create(self, args):
        return Alert(TNCHeartbeatConnectionFailureAlertClass, args)

    async def delete(self, alerts, query):
        return []


class TNCDisabledAutoUnconfiguredAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.ERROR
    category = AlertCategory.TRUENAS_CONNECT
    title = 'TrueNAS Connect Disabled - Service Unconfigured'
    text = 'TrueNAS Connect has been disabled from TrueNAS Connect. The system has automatically unconfigured itself.'

    async def create(self, args):
        return Alert(TNCDisabledAutoUnconfiguredAlertClass, args)

    async def delete(self, alerts, query):
        return []
