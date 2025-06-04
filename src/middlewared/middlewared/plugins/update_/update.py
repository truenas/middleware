import errno
import os
import pathlib
import shutil

from middlewared.api import api_method
from middlewared.api.current import (
    UpdateFileArgs, UpdateFileResult,
    UpdateManualArgs, UpdateManualResult,
    UpdateRunArgs, UpdateRunResult,
)
from middlewared.service import job, private, CallError, Service, pass_app
from middlewared.plugins.update_.utils import UPLOAD_LOCATION

SYSTEM_UPGRADE_REBOOT_REASON = 'System upgrade'


class UpdateService(Service):

    @api_method(UpdateRunArgs, UpdateRunResult, roles=['SYSTEM_UPDATE_WRITE'])
    @job(lock='update')
    @pass_app(rest=True)
    async def run(self, app, job, attrs):
        """
        Downloads (if not already in cache) and apply an update.
        """
        location = await self.middleware.call('update.get_update_location')

        if attrs['resume']:
            options = {'raise_warnings': False}
        else:
            options = {}
            update = await self.middleware.call('update.download_update', job, attrs['train'], location, 50)
            if not update:
                raise CallError('No update available')

        await self.middleware.call('update.install', job, os.path.join(location, 'update.sqsh'), options)
        await self.middleware.call('cache.put', 'update.applied', True)
        await self.middleware.call_hook('update.post_run')

        if attrs['reboot']:
            await self.middleware.call('system.reboot', SYSTEM_UPGRADE_REBOOT_REASON, {'delay': 10}, app=app)

        return True

    @api_method(UpdateManualArgs, UpdateManualResult, roles=['SYSTEM_UPDATE_WRITE'])
    @job(lock='update')
    def manual(self, job, path, options):
        """
        Update the system using a manual update file.
        """
        if options.pop('resume'):
            options['raise_warnings'] = False

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
                self.middleware.call_sync(
                    'update.install', job, str(update_file.absolute()), options,
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
            if options['cleanup'] and unlink_file and os.path.exists(path):
                os.unlink(path)

        if path.startswith(UPLOAD_LOCATION):
            self.middleware.call_sync('update.destroy_upload_location')

        self.middleware.call_hook_sync('update.post_run')

    @private
    def file_impl(self, job, options):
        if options['resume']:
            update_options = {'raise_warnings': False}
        else:
            update_options = {}

        dest = options['destination']
        if not dest:
            if not options['resume']:
                try:
                    self.middleware.call_sync('update.create_upload_location')
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
            if options['resume']:
                if not os.path.exists(destfile):
                    raise CallError('There is no uploaded file to resume')
            else:
                job.check_pipe('input')
                job.set_progress(10, 'Writing uploaded file to disk')
                with open(destfile, 'wb') as f:
                    shutil.copyfileobj(job.pipes.input.r, f, 1048576)

            try:
                self.middleware.call_sync('update.install', job, destfile, update_options)
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
            self.middleware.call_sync('update.destroy_upload_location')

    @api_method(UpdateFileArgs, UpdateFileResult, roles=['SYSTEM_UPDATE_WRITE'])
    @job(lock='update')
    async def file(self, job, options):
        """
        Updates the system using the uploaded .tar file.
        """
        await self.middleware.run_in_thread(self.file_impl, job, options)
        await self.middleware.call_hook('update.post_run')
        job.set_progress(100, 'Update completed')
