from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, OneShotAlertClass


class CatalogNotHealthyAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.WARNING
    category = AlertCategory.APPLICATIONS
    title = 'Catalog Not Healthy'
    text = '%(apps)s Applications in %(catalog)s Catalog are not healthy.'

    async def create(self, args):
        return Alert(CatalogNotHealthyAlertClass, args, _key=args['catalog'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))


class CatalogSyncFailedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.CRITICAL
    category = AlertCategory.APPLICATIONS
    title = 'Unable to Sync Catalog'
    text = 'Failed to sync %(catalog)s catalog: %(error)s'

    async def create(self, args):
        return Alert(CatalogSyncFailedAlertClass, args, _key=args['catalog'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))
