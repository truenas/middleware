import errno
import os

from catalog_validation.validation import validate_catalog

from middlewared.schema import returns, Str
from middlewared.service import accepts, CallError, job, private, Service

from .validate_utils import check_errors


class CatalogService(Service):

    @accepts(Str('label'))
    @returns()
    @job(lock=lambda args: f'catalog_validate_{args[0]}')
    async def validate(self, job, label):
        """
        Validates `label` catalog format which includes validating trains and applications with their versions.

        This does not test if an app version is valid in terms of kubernetes resources but instead ensures it has
        the correct format and files necessary for TrueNAS to use it.
        """
        catalog = await self.middleware.call('catalog.get_instance', label)
        job.set_progress(10, f'Syncing {label} catalog')
        sync_job = await self.middleware.call('catalog.sync', label)
        await sync_job.wait()
        if sync_job.error:
            raise CallError(f'Failed to sync {label!r} catalog: {sync_job.error}')

        job.set_progress(50, f'Validating {label!r} catalog')
        await self.middleware.call('catalog.validate_catalog_from_path', catalog['location'])

    @private
    def validate_catalog_from_path(self, path):
        if not os.path.exists(path):
            raise CallError(f'{path!r} does not exist', errno=errno.ENOENT)

        check_errors(validate_catalog, path)
