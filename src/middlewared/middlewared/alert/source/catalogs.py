from dataclasses import dataclass

from middlewared.alert.base import AlertClass, AlertClassConfig, AlertCategory, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class CatalogNotHealthyAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.APPLICATIONS,
        level=AlertLevel.WARNING,
        title='Catalog Not Healthy',
        text='%(apps)s Applications in %(catalog)s Catalog are not healthy.',
        deleted_automatically=False,
    )

    apps: str
    catalog: str

    @classmethod
    def key(cls, args):
        return args['catalog']


@dataclass(kw_only=True)
class CatalogSyncFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.APPLICATIONS,
        level=AlertLevel.CRITICAL,
        title='Unable to Sync Catalog',
        text='Failed to sync %(catalog)s catalog: %(error)s',
        deleted_automatically=False,
    )

    catalog: str
    error: str

    @classmethod
    def key(cls, args):
        return args['catalog']
