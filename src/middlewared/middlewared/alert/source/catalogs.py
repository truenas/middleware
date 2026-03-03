from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, OneShotAlertClass


class CatalogNotHealthyAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.WARNING
    category = AlertCategory.APPLICATIONS
    title = 'Catalog Not Healthy'
    text = '%(apps)s Applications in %(catalog)s Catalog are not healthy.'

    @classmethod
    def key(cls, args):
        return args['catalog']


class CatalogSyncFailedAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    level = AlertLevel.CRITICAL
    category = AlertCategory.APPLICATIONS
    title = 'Unable to Sync Catalog'
    text = 'Failed to sync %(catalog)s catalog: %(error)s'

    @classmethod
    def key(cls, args):
        return args['catalog']
