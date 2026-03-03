from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, SimpleOneShotAlertClass


class CatalogNotHealthyAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.WARNING
    category = AlertCategory.APPLICATIONS
    title = 'Catalog Not Healthy'
    text = '%(apps)s Applications in %(catalog)s Catalog are not healthy.'

    def key(self, args):
        return args['catalog']


class CatalogSyncFailedAlertClass(AlertClass, SimpleOneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.CRITICAL
    category = AlertCategory.APPLICATIONS
    title = 'Unable to Sync Catalog'
    text = 'Failed to sync %(catalog)s catalog: %(error)s'

    def key(self, args):
        return args['catalog']
