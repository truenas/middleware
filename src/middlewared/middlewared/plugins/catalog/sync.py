import os

from middlewared.schema import accepts, Str
from middlewared.service import CallError, job, private, returns, Service

from .git_utils import pull_clone_repository
from .utils import OFFICIAL_LABEL


class CatalogService(Service):

    SYNCED = False

    @private
    async def synced(self):
        return self.SYNCED

    @accepts()
    @returns()
    @job(lock='sync_catalogs')
    async def sync_all(self, job):
        """
        Refresh all available catalogs from upstream.
        """
        filters = [] if await self.middleware.call('catalog.dataset_mounted') else [['id', '=', OFFICIAL_LABEL]]
        catalogs = await self.middleware.call('catalog.query', filters)
        catalog_len = len(catalogs)
        for index, catalog in enumerate(catalogs):
            job.set_progress((index / catalog_len) * 100, f'Syncing {catalog["id"]} catalog')
            sync_job = await self.middleware.call('catalog.sync', catalog['id'])
            await sync_job.wait()

        self.SYNCED = True

    @accepts(Str('label', required=True))
    @returns()
    @job(lock=lambda args: f'{args[0]}_catalog_sync')
    async def sync(self, job, catalog_label):
        """
        Sync `label` catalog to retrieve latest changes from upstream.
        """
        try:
            catalog = await self.middleware.call('catalog.get_instance', catalog_label)
            if catalog_label != OFFICIAL_LABEL and not await self.middleware.call('catalog.dataset_mounted'):
                raise CallError(
                    'Cannot sync non-official catalogs when apps are not configured or catalog dataset is not mounted'
                )

            job.set_progress(5, 'Updating catalog repository')
            await self.middleware.call('catalog.update_git_repository', catalog)
            job.set_progress(15, 'Reading catalog information')
            if catalog_label == OFFICIAL_LABEL:
                # Update feature map cache whenever official catalog is updated
                await self.middleware.call('catalog.get_feature_map', False)
                await self.middleware.call('catalog.retrieve_recommended_apps', False)

            await self.middleware.call('catalog.apps', catalog_label, {
                'cache': False,
                'cache_only': False,
                'retrieve_all_trains': True,
                'trains': [],
            })
        except Exception as e:
            await self.middleware.call(
                'alert.oneshot_create', 'CatalogSyncFailed', {'catalog': catalog_label, 'error': str(e)}
            )
            raise
        else:
            await self.middleware.call('alert.oneshot_delete', 'CatalogSyncFailed', catalog_label)
            job.set_progress(100, f'Synced {catalog_label!r} catalog')

    @private
    def update_git_repository(self, catalog):
        self.middleware.call_sync('network.general.will_perform_activity', 'catalog')
        return pull_clone_repository(
            catalog['repository'], os.path.dirname(catalog['location']), catalog['branch'],
        )
