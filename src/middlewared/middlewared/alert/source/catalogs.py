from middlewared.alert.base import AlertClass, AlertClassConfig, AlertCategory, AlertLevel, OneShotAlertClass


class CatalogNotHealthyAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.APPLICATIONS,
        level=AlertLevel.WARNING,
        title='Catalog Not Healthy',
        text='%(apps)s Applications in %(catalog)s Catalog are not healthy.',
        deleted_automatically=False,
    )

    @classmethod
    def key(cls, args):
        return args['catalog']


class CatalogSyncFailedAlert(AlertClass, OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.APPLICATIONS,
        level=AlertLevel.CRITICAL,
        title='Unable to Sync Catalog',
        text='Failed to sync %(catalog)s catalog: %(error)s',
        deleted_automatically=False,
    )

    @classmethod
    def key(cls, args):
        return args['catalog']
