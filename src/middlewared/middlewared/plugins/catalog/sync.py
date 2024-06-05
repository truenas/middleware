import os

from middlewared.schema import accepts
from middlewared.service import job, private, returns, Service

from .git_utils import pull_clone_repository
from .utils import OFFICIAL_LABEL, OFFICIAL_CATALOG_REPO, OFFICIAL_CATALOG_BRANCH


class CatalogService(Service):

    SYNCED = False

    @private
    async def synced(self):
        return self.SYNCED

    @accepts()
    @returns()
    @job(lock='official_catalog_sync')
    async def sync(self, job):
        """
        Sync truenas catalog to retrieve latest changes from upstream.
        """
        try:
            catalog = await self.middleware.call('catalog.config')

            job.set_progress(5, 'Updating catalog repository')
            await self.middleware.call('catalog.update_git_repository', {
                **catalog,
                'repository': OFFICIAL_CATALOG_REPO,
                'branch': OFFICIAL_CATALOG_BRANCH,
            })
            job.set_progress(15, 'Reading catalog information')
            # Update feature map cache whenever official catalog is updated
            await self.middleware.call('catalog.get_feature_map', False)
            await self.middleware.call('catalog.retrieve_recommended_apps', False)

            await self.middleware.call('catalog.apps', {
                'cache': False,
                'cache_only': False,
                'retrieve_all_trains': True,
                'trains': [],
            })
        except Exception as e:
            await self.middleware.call(
                'alert.oneshot_create', 'CatalogSyncFailed', {'catalog': OFFICIAL_LABEL, 'error': str(e)}
            )
            raise
        else:
            await self.middleware.call('alert.oneshot_delete', 'CatalogSyncFailed', OFFICIAL_LABEL)
            job.set_progress(100, f'Synced {OFFICIAL_LABEL!r} catalog')
            self.SYNCED = True

    @private
    def update_git_repository(self, catalog):
        self.middleware.call_sync('network.general.will_perform_activity', 'catalog')
        return pull_clone_repository(
            catalog['repository'], os.path.dirname(catalog['location']), catalog['branch'],
        )
