from __future__ import annotations

import errno
import os
import pathlib
import shutil
import typing

from middlewared.api import api_method
from middlewared.api.current import (
    UpdateFileOptions, UpdateFileArgs, UpdateFileResult,
    UpdateManualOptions, UpdateManualArgs, UpdateManualResult,
    UpdateRunAttrs, UpdateRunArgs, UpdateRunResult,
)
from middlewared.service import job, private, CallError, Service
from middlewared.plugins.update_.utils import UPLOAD_LOCATION

if typing.TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job

SYSTEM_UPGRADE_REBOOT_REASON = 'System upgrade'


class UpdateService(Service):

    @api_method(
        UpdateRunArgs,
        UpdateRunResult,
        roles=['SYSTEM_UPDATE_WRITE'],
        pass_app=True,
        check_annotations=True,
    )
    @job(lock='update')
    async def run(self, app: App, job: Job, attrs: UpdateRunAttrs) -> typing.Literal[True]:
        """
        Downloads (if not already in cache) and apply an update.
        """
        location = await self.call2(self.s.update.get_update_location)

        if attrs.resume:
            options = {'raise_warnings': False}
        else:
            options = {}
            update = await self.call2(self.s.update.download_update, job, attrs.train, attrs.version, location, 50)
            if not update:
                raise CallError('No update available')

        await self.call2(self.s.update.install, job, os.path.join(location, 'update.sqsh'), options)
        await self.middleware.call('cache.put', 'update.applied', True)
        await self.middleware.call_hook('update.post_run')

        if attrs.reboot:
            await self.middleware.call('system.reboot', SYSTEM_UPGRADE_REBOOT_REASON, {'delay': 10}, app=app)

        return True

    @api_method(
        UpdateManualArgs,
        UpdateManualResult,
        roles=['SYSTEM_UPDATE_WRITE'],
        check_annotations=True,
    )
    @job(lock='update')
    def manual(self, job: Job, path: str, options: UpdateManualOptions) -> None:
        """
        Update the system using a manual update file.
        """
        options_dict = options.model_dump()
        if options_dict.pop('resume'):
            options_dict['raise_warnings'] = False

        update_file = pathlib.Path(path)

        # make sure absolute path was given
        if not update_file.is_absolute():
            raise CallError('Absolute path must be provided.', errno.ENOENT)

        # make sure file exists
        if not update_file.exists():
            raise CallError('File does not exist.', errno.ENOENT)

        unlink_file = True
        try:
            try:
                # We use 90 as max progress here because we will set it to 95 after this completes
                # in cleanup - otherwise scale build will give 100 and then we will go back to 95
                self.call_sync2(
                    self.s.update.install, job, str(update_file.absolute()), options_dict, 90,
                )
            except Exception as e:
                if isinstance(e, CallError):
                    if e.errno == errno.EAGAIN:
                        unlink_file = False

                    raise
                else:
                    self.logger.debug('Applying manual update failed', exc_info=True)
                    raise CallError(str(e), errno.EFAULT)

            job.set_progress(95, 'Cleaning up')
        finally:
            if options.cleanup and unlink_file and os.path.exists(path):
                os.unlink(path)

        if path.startswith(UPLOAD_LOCATION):
            self.call_sync2(self.s.update.destroy_upload_location)

        self.middleware.call_hook_sync('update.post_run')
        job.set_progress(100, 'Update completed')

    @private
    def file_impl(self, job: Job, options: UpdateFileOptions) -> None:
        if options.resume:
            update_options = {'raise_warnings': False}
        else:
            update_options = {}

        dest = options.destination
        if not dest:
            if not options.resume:
                try:
                    self.call_sync2(self.s.update.create_upload_location)
                except Exception as e:
                    raise CallError(str(e))
            dest = UPLOAD_LOCATION
        elif not dest.startswith('/mnt/'):
            raise CallError(f'Destination: {dest!r} must reside within a pool')

        if not os.path.isdir(dest):
            raise CallError(f'Destination: {dest!r} is not a directory')

        destfile = os.path.join(dest, 'manualupdate.sqsh')

        unlink_destfile = True
        try:
            if options.resume:
                if not os.path.exists(destfile):
                    raise CallError('There is no uploaded file to resume')
            else:
                job.check_pipe('input')
                job.set_progress(10, 'Writing uploaded file to disk')
                with open(destfile, 'wb') as f:
                    shutil.copyfileobj(job.pipes.input.r, f, 1048576)

            try:
                # We use 90 as max progress here because we will set it to 95 after this completes
                # in cleanup - otherwise scale build will give 100 and then we will go back to 95
                self.call_sync2(self.s.update.install, job, destfile, update_options, 90)
            except CallError as e:
                if e.errno == errno.EAGAIN:
                    unlink_destfile = False
                raise
            job.set_progress(95, 'Cleaning up')
        finally:
            if unlink_destfile:
                if os.path.exists(destfile):
                    os.unlink(destfile)

        if dest == UPLOAD_LOCATION:
            self.call_sync2(self.s.update.destroy_upload_location)

    @api_method(
        UpdateFileArgs,
        UpdateFileResult,
        roles=['SYSTEM_UPDATE_WRITE'],
        check_annotations=True,
    )
    @job(lock='update')
    async def file(self, job: Job, options: UpdateFileOptions) -> None:
        """
        Updates the system using the uploaded .tar file.
        """
        await self.call2(self.s.update.file_impl, job, options)
        await self.middleware.call_hook('update.post_run')
        job.set_progress(100, 'Update completed')
