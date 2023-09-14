# -*- coding=utf-8 -*-
import contextlib
import os
import shutil
import subprocess

from freenasOS import Configuration, Manifest, Update

from middlewared.service import CallError, job, private, Service
from middlewared.worker import FakeJob

from .utils import can_update
from .utils_freebsd import UpdateHandler

run_kw = dict(check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', errors='ignore')


class UpdateService(Service):
    @private
    def install_impl(self, job, location):
        if os.path.exists(os.path.join(location, 'scale')):
            return self._install_scale(job, os.path.join(location, 'update.sqsh'))

        old_manifest = Configuration.Configuration().SystemManifest()

        new_manifest = Manifest.Manifest(require_signature=True)
        try:
            new_manifest.LoadPath('{}/MANIFEST'.format(location))
        except FileNotFoundError:
            raise CallError('Uploaded file is not a manual update file')

        old_version = old_manifest.Version()
        new_version = new_manifest.Version()
        if old_version == new_version:
            raise CallError(f'You already are using {new_version}')
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
        p = subprocess.run(['file', path], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, encoding='ascii',
                           errors='ignore')
        if 'Squashfs filesystem' in p.stdout:
            if self.middleware.call_sync('system.is_enterprise'):
                try:
                    allowed = self.middleware.call_sync('cache.get', 'TRUENAS_ENT_UPGRADE') == 1
                except KeyError:
                    allowed = False

                if not allowed:
                    raise CallError('Enterprise upgrade to SCALE not allowed')
            return self._install_scale(job, path)

        job.set_progress(30, 'Extracting file')
        Update.ExtractFrozenUpdate(path, dest_extracted, verbose=True)

        job.set_progress(50, 'Applying update')
        if self.install_impl(job, dest_extracted) is None:
            raise CallError('Uploaded file is not a manual update file')

    def _install_scale(self, job, path):
        if self.middleware.call_sync('system.product_type') == 'ENTERPRISE':
            minio = self.middleware.call_sync('service.query', [('service', '=', 's3')], {'get': True})
            if minio['enable'] or minio['state'] == 'RUNNING':
                raise CallError(
                    "There are active configured services on this system that are not present in the new version. To "
                    "avoid any loss of system services, please contact iXsystems Support to schedule a guided upgrade. "
                    "Additional details are available from https://www.truenas.com/docs/scale/scaledeprecatedfeatures/."
                )

        location = os.path.dirname(path)

        mounted = os.path.join(location, 'squashfs-root')
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(mounted)

        job.set_progress(0, 'Extracting update file')
        subprocess.run(['unsquashfs', os.path.basename(path)], cwd=location, **run_kw)

        try:
            return self.middleware.call_sync(
                'update.install_scale',
                mounted,
                lambda progress, description: job.set_progress((0.5 + 0.5 * progress) * 100, description),
            )
        finally:
            shutil.rmtree(mounted)
