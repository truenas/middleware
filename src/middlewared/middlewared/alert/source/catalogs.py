from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class CatalogNotHealthyAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.APPLICATIONS,
        level=AlertLevel.WARNING,
        title="Catalog Not Healthy",
        text="%(apps)s Applications in %(catalog)s Catalog are not healthy.",
        deleted_automatically=False,
    )

    apps: str
    catalog: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args["catalog"]


@dataclass(kw_only=True)
class CatalogSyncFailedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.APPLICATIONS,
        level=AlertLevel.CRITICAL,
        title="Unable to Sync Catalog",
        text="Failed to sync %(catalog)s catalog: %(error)s",
        deleted_automatically=False,
    )

    catalog: str
    error: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args["catalog"]
