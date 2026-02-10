from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    CatalogApps, CatalogAppsArgs, CatalogAppsResponse, CatalogAppsResult, CatalogEntry,
    CatalogTrainsArgs, CatalogTrainsResult, CatalogTrainsResponse, CatalogUpdate,
    CatalogUpdateArgs, CatalogUpdateResult, CatalogSyncArgs, CatalogSyncResult,
    CatalogAppVersionDetails, CatalogGetAppDetailsArgs, CatalogGetAppDetailsResult,
    CatalogAppInfo,
)
from middlewared.plugins.docker.state_utils import catalog_ds_path
from middlewared.service import ConfigService, job, private

from .config import CatalogConfigPart
from .apps_details import apps as apps_impl
from .app_version import get_app_details
from .state import dataset_mounted
from .sync import sync as sync_impl
from .utils import TMP_IX_APPS_CATALOGS


__all__ = ('CatalogService',)


if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


class CatalogService(ConfigService):

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
    def get_app_details(self, app_name: str, options: CatalogAppVersionDetails) -> CatalogAppInfo:
        """
        Retrieve information of `app_name` `app_version_details.catalog` catalog app.
        """
        return get_app_details(self.context, app_name, options)

    @api_method(CatalogSyncArgs, CatalogSyncResult, roles=['CATALOG_WRITE'])
    @job(lock='official_catalog_sync', lock_queue_size=0)
    async def sync(self, job: Job) -> None:
        """
        Sync truenas catalog to retrieve latest changes from upstream.
        """
        return await sync_impl(self.context, job)

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
    def extend(self, data, context):
        data.update({
            'id': data['label'],
            'location': context['catalog_dir'],
        })
        return data

    @private
    async def extend_context(self, rows, extra):
        if await dataset_mounted(self.context):
            catalog_dir = catalog_ds_path()
        else:
            # FIXME: This can eat lots of memory if it's a large catalog
            catalog_dir = TMP_IX_APPS_CATALOGS

        return {
            'catalog_dir': catalog_dir,
        }

    @private
    async def update_train_for_enterprise(self) -> None:
        return await self._config_part.update_train_for_enterprise()


async def setup(middleware: Middleware) -> None:
    await middleware.call('network.general.register_activity', 'catalog', 'Catalog(s) information')
