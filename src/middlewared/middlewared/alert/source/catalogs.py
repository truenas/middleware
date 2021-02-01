from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, OneShotAlertClass


class CatalogNotHealthyAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.CRITICAL
    category = AlertCategory.APPLICATIONS
    title = 'Catalog Not Healthy'
    text = '%(apps)s are not healthy'

    async def create(self, args):
        return Alert(CatalogNotHealthyAlertClass, args, key=args['catalog'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))
