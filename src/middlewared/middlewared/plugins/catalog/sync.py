import aiohttp

from middlewared.api import api_method
from middlewared.api.current import CatalogSyncArgs, CatalogSyncResult
from middlewared.service import job, private, Service

from .git_utils import pull_clone_repository
from .utils import OFFICIAL_LABEL, OFFICIAL_CATALOG_REPO, OFFICIAL_CATALOG_BRANCH


STATS_URL = 'https://telemetry.sys.truenas.net/apps/truenas-apps-stats.json'


class CatalogService(Service):

    POPULARITY_INFO = {}
    SYNCED = False

    @private
    async def update_popularity_cache(self):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            try:
                async with session.get(STATS_URL) as response:
                    response.raise_for_status()
                    self.POPULARITY_INFO = {
                        k.lower(): v for k, v in (await response.json()).items()
                        # Making sure we have a consistent format as for trains we see capitalized
                        # entries in the file
                    }
            except Exception as e:
                self.logger.error('Failed to fetch popularity stats for apps: %r', e)

    @private
    async def popularity_cache(self):
        return self.POPULARITY_INFO

    @private
    async def synced(self):
        return self.SYNCED

    @api_method(CatalogSyncArgs, CatalogSyncResult, roles=['CATALOG_WRITE'])
    @job(lock='official_catalog_sync', lock_queue_size=1)
    async def sync(self, job):
        """
        Sync truenas catalog to retrieve latest changes from upstream.
        """
        try:
            catalog = await self.middleware.call('catalog.config')

            job.set_progress(5, 'Updating catalog repository')
            await self.middleware.call(
                'catalog.update_git_repository', catalog['location'], OFFICIAL_CATALOG_REPO, OFFICIAL_CATALOG_BRANCH
            )
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
            await self.update_popularity_cache()
        except Exception as e:
            await self.middleware.call(
                'alert.oneshot_create', 'CatalogSyncFailed', {'catalog': OFFICIAL_LABEL, 'error': str(e)}
            )
            raise
        else:
            await self.middleware.call('alert.oneshot_delete', 'CatalogSyncFailed', OFFICIAL_LABEL)
            job.set_progress(100, f'Synced {OFFICIAL_LABEL!r} catalog')
            self.SYNCED = True
            self.middleware.create_task(self.middleware.call('app.check_upgrade_alerts'))

    @private
    async def update_git_repository(self, location, repository, branch):
        await self.middleware.call('network.general.will_perform_activity', 'catalog')
        return await self.middleware.run_in_thread(pull_clone_repository, repository, location, branch)
