from __future__ import annotations

import errno
import os
import pathlib
import shutil
import typing

from middlewared.api.current import UpdateFileOptions, UpdateManualOptions, UpdateRunAttrs
from middlewared.service import CallError, ServiceContext
from middlewared.plugins.update_.utils import UPLOAD_LOCATION
from .download import download_update, get_update_location
from .install_linux import install
from .upload_location_linux import create_upload_location, destroy_upload_location

if typing.TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job

SYSTEM_UPGRADE_REBOOT_REASON = 'System upgrade'


async def run(context: ServiceContext, app: App, job: Job, attrs: UpdateRunAttrs) -> typing.Literal[True]:
    location = await context.to_thread(get_update_location, context)

    if attrs.resume:
        options = {'raise_warnings': False}
    else:
        options = {}
        update = await context.to_thread(download_update, context, job, attrs.train, attrs.version, location, 50)
        if not update:
            raise CallError('No update available')

    await context.to_thread(install, context, job, os.path.join(location, 'update.sqsh'), options)
    await context.middleware.call('cache.put', 'update.applied', True)
    await context.middleware.call_hook('update.post_run')

    if attrs.reboot:
        await context.middleware.call('system.reboot', SYSTEM_UPGRADE_REBOOT_REASON, {'delay': 10}, app=app)

    return True


def manual(context: ServiceContext, job: Job, path: str, options: UpdateManualOptions) -> None:
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
            install(context, job, str(update_file.absolute()), options_dict, 90)
        except Exception as e:
            if isinstance(e, CallError):
                if e.errno == errno.EAGAIN:
                    unlink_file = False

                raise
            else:
                context.logger.debug('Applying manual update failed', exc_info=True)
                raise CallError(str(e), errno.EFAULT)

        job.set_progress(95, 'Cleaning up')
    finally:
        if options.cleanup and unlink_file and os.path.exists(path):
            os.unlink(path)

    if path.startswith(UPLOAD_LOCATION):
        destroy_upload_location(context)

    context.middleware.call_hook_sync('update.post_run')
    job.set_progress(100, 'Update completed')


def file_impl(context: ServiceContext, job: Job, options: UpdateFileOptions) -> None:
    if options.resume:
        update_options = {'raise_warnings': False}
    else:
        update_options = {}

    dest = options.destination
    if not dest:
        if not options.resume:
            try:
                create_upload_location(context)
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
            install(context, job, destfile, update_options, 90)
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
        destroy_upload_location(context)


async def file(context: ServiceContext, job: Job, options: UpdateFileOptions) -> None:
    await context.to_thread(file_impl, context, job, options)
    await context.middleware.call_hook('update.post_run')
    job.set_progress(100, 'Update completed')
