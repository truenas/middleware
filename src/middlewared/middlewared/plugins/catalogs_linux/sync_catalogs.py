import asyncio
import os

from middlewared.schema import accepts, Str, returns
from middlewared.service import job, private, Service

from .utils import pull_clone_repository


class CatalogService(Service):

    @accepts()
    @returns()
    @job(lock='sync_catalogs')
    async def sync_all(self, job):
        """
        Refresh all available catalogs from upstream.
        """
        catalogs = await self.middleware.call('catalog.query')
        catalog_len = len(catalogs)
        for index, catalog in enumerate(catalogs):
            job.set_progress((index / catalog_len) * 100, f'Syncing {catalog["id"]} catalog')
            sync_job = await self.middleware.call('catalog.sync', catalog['id'])
            await sync_job.wait()

        if await self.middleware.call('kubernetes.validate_k8s_setup', False):
            asyncio.ensure_future(self.middleware.call('chart.release.chart_releases_update_checks_internal'))

    @accepts(Str('label', required=True))
    @returns()
    @job(lock=lambda args: f'{args[0]}_catalog_sync')
    async def sync(self, job, catalog_label):
        """
        Sync `label` catalog to retrieve latest changes from upstream.
        """
        try:
            catalog = await self.middleware.call('catalog.get_instance', catalog_label)
            job.set_progress(5, 'Updating catalog repository')
            await self.middleware.call('catalog.update_git_repository', catalog)
            job.set_progress(15, 'Reading catalog information')
            item_job = await self.middleware.call('catalog.items_internal', catalog_label, await self.sync_items_params())
            await item_job.wait(raise_error=True)
        except Exception as e:
            await self.middleware.call(
                'alert.oneshot_create', 'CatalogSyncFailed', {'catalog': catalog_label, 'error': str(e)}
            )
            raise
        else:
            await self.middleware.call('alert.oneshot_delete', 'CatalogSyncFailed', catalog_label)
            job.set_progress(100, f'Synced {catalog_label!r} catalog')

    @private
    async def sync_items_params(self):
        return {
            'cache': False,
            'cache_only': False,
            'retrieve_all_trains': True,
            'trains': [],
        }

    @private
    def update_git_repository(self, catalog):
        self.middleware.call_sync('network.general.will_perform_activity', 'catalog')
        return pull_clone_repository(
            catalog['repository'], os.path.dirname(catalog['location']), catalog['branch'],
        )
