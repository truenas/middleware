from __future__ import annotations

from typing import Any, TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    CatalogApps, CatalogAppsArgs, CatalogAppsResponse, CatalogAppsResult, CatalogEntry,
    CatalogTrainsArgs, CatalogTrainsResult, CatalogTrainsResponse, CatalogUpdate,
    CatalogUpdateArgs, CatalogUpdateResult, CatalogSyncArgs, CatalogSyncResult,
    CatalogSyncedArgs, CatalogSyncedResult,
    CatalogAppDetails, CatalogAppVersionDetails, CatalogGetAppDetailsArgs, CatalogGetAppDetailsResult,
)
from middlewared.service import ConfigService, job, private

from .config import CatalogConfigPart
from .apps_details import (
    apps as apps_impl,
    app_version_details as app_version_details_impl,
    get_normalized_questions_context as get_nqc_impl,
    train_to_apps_version_mapping as train_to_apps_version_mapping_impl,
    NormalizedQuestions,
)
from .app_version import get_app_details
from .features import version_supported_error_check as version_supported_error_check_impl
from .sync import get_synced_state, sync as sync_impl


__all__ = ('CatalogService',)


if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


class CatalogService(ConfigService[CatalogEntry]):
    class Config:
        cli_namespace = 'app.catalog'
        role_prefix = 'CATALOG'
        entry = CatalogEntry
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._config_part = CatalogConfigPart(self.context)

    async def config(self) -> CatalogEntry:
        return await self._config_part.config()

    @api_method(CatalogUpdateArgs, CatalogUpdateResult, check_annotations=True)
    async def do_update(self, data: CatalogUpdate) -> CatalogEntry:
        """
        Update catalog preferences.
        """
        return await self._config_part.do_update(data)

    @api_method(
        CatalogGetAppDetailsArgs, CatalogGetAppDetailsResult,
        roles=['CATALOG_READ'], check_annotations=True,
    )
    def get_app_details(self, app_name: str, options: CatalogAppVersionDetails) -> CatalogAppDetails:
        """
        Retrieve information of `app_name` `app_version_details.catalog` catalog app.
        """
        return get_app_details(self.context, app_name, options)

    @api_method(CatalogSyncArgs, CatalogSyncResult, roles=['CATALOG_WRITE'], check_annotations=True)
    @job(lock='official_catalog_sync', lock_queue_size=0)
    async def sync(self, job: Job) -> None:
        """
        Sync truenas catalog to retrieve latest changes from upstream.
        """
        return await sync_impl(self.context, job)

    @api_method(CatalogSyncedArgs, CatalogSyncedResult, check_annotations=True, roles=['CATALOG_READ'])
    def synced(self) -> bool:
        """
        Return whether the catalog has been synced at least once.
        """
        return get_synced_state()

    @api_method(CatalogAppsArgs, CatalogAppsResult, check_annotations=True, roles=['CATALOG_READ'])
    def apps(self, options: CatalogApps) -> CatalogAppsResponse:
        """
        Retrieve apps details for `label` catalog.

        `options.cache` is a boolean which when set will try to get apps details for `label` catalog from cache
        if available.

        `options.cache_only` is a boolean which when set will force usage of cache only for retrieving catalog
        information. If the content for the catalog in question is not cached, no content would be returned. If
        `options.cache` is unset, this attribute has no effect.

        `options.retrieve_all_trains` is a boolean value which when set will retrieve information for all the trains
        present in the catalog ( it is set by default ).

        `options.trains` is a list of train name(s) which will allow selective filtering to retrieve only information
        of desired trains in a catalog. If `options.retrieve_all_trains` is set, it has precedence over `options.train`.
        """
        return apps_impl(self.context, options)

    @api_method(CatalogTrainsArgs, CatalogTrainsResult, check_annotations=True, roles=['CATALOG_READ'])
    def trains(self) -> CatalogTrainsResponse:
        """
        Retrieve available trains.
        """
        return CatalogTrainsResponse.model_validate(
            list(apps_impl(self.context, CatalogApps(cache=True, cache_only=True)).root)
        )

    @private
    def train_to_apps_version_mapping(self) -> dict[str, dict[str, dict[str, str | None]]]:
        return train_to_apps_version_mapping_impl(self.context)

    @private
    async def get_normalized_questions_context(self) -> NormalizedQuestions:
        return await get_nqc_impl(self.context)

    @private
    def app_version_details(self, version_path: str, questions_context: NormalizedQuestions | None = None) -> dict[str, Any]:
        return app_version_details_impl(self.context, version_path, questions_context)

    @private
    async def version_supported_error_check(self, version_details: dict[str, Any]) -> None:
        await version_supported_error_check_impl(self.context, version_details)

    @private
    async def update_train_for_enterprise(self) -> None:
        return await self._config_part.update_train_for_enterprise()


async def setup(middleware: Middleware) -> None:
    await middleware.call('network.general.register_activity', 'catalog', 'Catalog(s) information')
