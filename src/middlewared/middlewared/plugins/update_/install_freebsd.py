# -*- coding=utf-8 -*-
from freenasOS import Configuration, Manifest, Update

from middlewared.service import CallError, job, private, Service
from middlewared.worker import FakeJob

from .utils import can_update
from .utils_freebsd import UpdateHandler


class UpdateService(Service):
    @private
    def install_impl(self, job, location):
        old_manifest = Configuration.Configuration().SystemManifest()

        new_manifest = Manifest.Manifest(require_signature=True)
        new_manifest.LoadPath('{}/MANIFEST'.format(location))

        old_version = old_manifest.Version()
        new_version = new_manifest.Version()
        if not can_update(old_version, new_version):
            raise CallError(f'Unable to downgrade from {old_version} to {new_version}')

        return self.middleware.call_sync('update.install_impl_job', job.id, location).wait_sync(raise_error=True)

    @private
    @job(process=True)
    def install_impl_job(self, job, job_id, location):
        job = FakeJob(job_id, self.middleware.client)

        handler = UpdateHandler(self, job)

        return Update.ApplyUpdate(
            location,
            install_handler=handler.install_handler,
        )

    @private
    def install_manual_impl(self, job, path, dest_extracted):
        job.set_progress(30, 'Extracting file')
        Update.ExtractFrozenUpdate(path, dest_extracted, verbose=True)

        job.set_progress(50, 'Applying update')
        if self.install_impl(job, dest_extracted) is None:
            raise CallError('Uploaded file is not a manual update file')
