from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import CatalogEntry
from middlewared.plugins.docker.state_utils import catalog_ds_path
from middlewared.service import ConfigService, private

from .config import CatalogConfigPart
from .state import dataset_mounted
from .utils import TMP_IX_APPS_CATALOGS


__all__ = ('CatalogService',)


if TYPE_CHECKING:
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


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'catalog', 'Catalog(s) information')
