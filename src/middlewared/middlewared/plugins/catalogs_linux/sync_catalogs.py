import asyncio
import os

from middlewared.schema import accepts, Str
from middlewared.service import job, private, Service

from .utils import pull_clone_repository


class CatalogService(Service):

    @accepts()
    @job(lock='sync_catalogs')
    async def sync_all(self, job):
        """
        Refresh all available catalogs from upstream.
        """
        catalogs = await self.middleware.call('catalog.query')
        catalog_len = len(catalogs)
        for index, catalog in enumerate(catalogs):
            job.set_progress(((index + 1) / catalog_len) * 100, f'Syncing {catalog["id"]} catalog')
            try:
                await self.middleware.call('catalog.sync', catalog['id'])
            except Exception as e:
                self.logger.error('Failed to sync %r catalog: %s', catalog['id'], e)

        if await self.middleware.call('service.started', 'kubernetes'):
            asyncio.ensure_future(self.middleware.call('chart.release.chart_releases_update_checks_internal'))

    @accepts(Str('label', required=True))
    async def sync(self, catalog_label):
        """
        Sync `label` catalog to retrieve latest changes from upstream.
        """
        catalog = await self.middleware.call('catalog.get_instance', catalog_label)
        await self.middleware.call('catalog.update_git_repository', catalog, True)
        await self.middleware.call('catalog.items', catalog_label, {'cache': False})

    @private
    def update_git_repository(self, catalog, raise_exception=False):
        return pull_clone_repository(
            catalog['repository'], os.path.dirname(catalog['location']), catalog['branch'],
            raise_exception=raise_exception,
        )
