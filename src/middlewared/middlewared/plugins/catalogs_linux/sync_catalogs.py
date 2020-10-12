import contextlib
import os

from middlewared.schema import accepts, Str
from middlewared.service import CallError, job, periodic, private, Service

from .utils import pull_clone_repository


class CatalogService(Service):

    @accepts()
    @periodic(interval=864000)
    @job(lock='sync_catalogs')
    async def sync_catalogs(self, job):
        catalogs = await self.middleware.call('catalog.query')
        for catalog in catalogs:
            job.set_progress(100 / len(catalogs), f'Syncing {catalog["id"]} catalog')
            with contextlib.suppress(Exception):
                await self.middleware.call('catalog.sync', catalog['id'])

    @accepts(Str('label', required=True))
    def sync(self, catalog_label):
        catalog = self.middleware.call_sync('catalog.get_instance', catalog_label)
        sync_failure = False
        error_str = f'Unable to sync {catalog_label} catalog. Please refer to logs.'
        if not self.update_git_repository(catalog):
            self.logger.error('Failed to sync %r catalog', catalog['id'])
            # If we had an earlier version of cloned catalog repo, let's sync our cache with those contents
            if not os.path.exists(catalog['location']):
                raise CallError(error_str)
            else:
                sync_failure = True

        # TODO: update cache

        if sync_failure:
            raise CallError(error_str)

    @private
    def update_git_repository(self, catalog, raise_exception=False):
        return pull_clone_repository(
            catalog['repository'], os.path.dirname(catalog['location']), catalog['branch'],
            raise_exception=raise_exception,
        )
