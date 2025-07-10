from middlewared.api import api_method
from middlewared.api.current import (
    UpdateCheckAvailableArgs, UpdateCheckAvailableResult, UpdateDownloadArgs, UpdateDownloadResult, UpdateFileArgs,
    UpdateFileResult, UpdateGetAutoDownloadArgs, UpdateGetAutoDownloadResult, UpdateGetPendingArgs,
    UpdateGetPendingResult, UpdateGetTrainsArgs, UpdateGetTrainsResult, UpdateManualArgs, UpdateManualResult,
    UpdateSetAutoDownloadArgs, UpdateSetAutoDownloadResult, UpdateSetTrainArgs, UpdateSetTrainResult, UpdateUpdateArgs,
    UpdateUpdateResult
)
from middlewared.service import job, private, CallError, Service, pass_app
import middlewared.sqlalchemy as sa
from middlewared.plugins.update_.utils import UPLOAD_LOCATION

import enum
import errno
import os
import shutil
import textwrap
import pathlib

SYSTEM_UPGRADE_REBOOT_REASON = 'System upgrade'


def parse_train_name(name):
    split = (name + '-').split('-')
    version = split[2]
    branch = split[3]

    return [version, branch]


class CompareTrainsResult(enum.Enum):
    MAJOR_DOWNGRADE = "MAJOR_DOWNGRADE"
    MAJOR_UPGRADE = "MAJOR_UPGRADE"
    NIGHTLY_DOWNGRADE = "NIGHTLY_DOWNGRADE"
    NIGHTLY_UPGRADE = "NIGHTLY_UPGRADE"


BAD_UPGRADES = {
    CompareTrainsResult.NIGHTLY_DOWNGRADE: textwrap.dedent("""\
        You're not allowed to change away from the nightly train, it is considered a downgrade.
        If you have an existing boot environment that uses that train, boot into it in order to upgrade
        that train.
    """),
    CompareTrainsResult.MAJOR_DOWNGRADE: textwrap.dedent("""\
        Downgrading TrueNAS installation is not supported.
        If you have an existing boot environment that uses that train, boot into it in order to upgrade
        that train.
    """),
}


def compare_trains(t1, t2):
    v1 = parse_train_name(t1)
    v2 = parse_train_name(t2)

    branch1 = v1[1].lower()
    branch2 = v2[1].lower()
    if branch1 != branch2:
        if branch2 == "nightlies":
            return CompareTrainsResult.NIGHTLY_UPGRADE
        elif branch1 == "nightlies":
            return CompareTrainsResult.NIGHTLY_DOWNGRADE

    if v1[0] != v2[0]:
        if v1[0] > v2[0]:
            return CompareTrainsResult.MAJOR_DOWNGRADE
        else:
            return CompareTrainsResult.MAJOR_UPGRADE


class UpdateModel(sa.Model):
    __tablename__ = 'system_update'

    id = sa.Column(sa.Integer(), primary_key=True)
    upd_autocheck = sa.Column(sa.Boolean(), default=True)
    upd_train = sa.Column(sa.String(50))


class UpdateService(Service):

    class Config:
        cli_namespace = 'system.update'

    @api_method(UpdateGetAutoDownloadArgs, UpdateGetAutoDownloadResult, roles=['SYSTEM_UPDATE_READ'])
    async def get_auto_download(self):
        """
        Returns if update auto-download is enabled.
        """
        return (await self.middleware.call('datastore.config', 'system.update'))['upd_autocheck']

    @api_method(UpdateSetAutoDownloadArgs, UpdateSetAutoDownloadResult, roles=['SYSTEM_UPDATE_WRITE'])
    async def set_auto_download(self, autocheck):
        """
        Sets if update auto-download is enabled.
        """
        config = await self.middleware.call('datastore.config', 'system.update')
        await self.middleware.call('datastore.update', 'system.update', config['id'], {'upd_autocheck': autocheck})
        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

    @api_method(UpdateGetTrainsArgs, UpdateGetTrainsResult, roles=['SYSTEM_UPDATE_READ'])
    def get_trains(self):
        """
        Returns available trains dict and the currently configured train as well as the
        train of currently booted environment.
        """
        self.middleware.call_sync('network.general.will_perform_activity', 'update')

        data = self.middleware.call_sync('datastore.config', 'system.update')

        trains_data = self.middleware.call_sync('update.get_trains_data')
        current_train = trains_data['current_train']
        trains = trains_data['trains']
        selected = None
        for name, train in list(trains.items()):
            try:
                result = compare_trains(current_train, name)
            except Exception:
                self.logger.warning(
                    "Failed to compare trains %r and %r", current_train, name, exc_info=True
                )
                continue
            else:
                if result in BAD_UPGRADES:
                    trains.pop(name)
                    continue

            if not selected and data['upd_train'] == name:
                selected = data['upd_train']
            if name in trains_data['trains_redirection']:
                trains.pop(name)
                continue
        if not data['upd_train'] or not selected:
            selected = current_train

        if selected in trains_data['trains_redirection']:
            selected = trains_data['trains_redirection'][selected]
        return {
            'trains': trains,
            'current': current_train,
            'selected': selected,
        }

    @api_method(UpdateSetTrainArgs, UpdateSetTrainResult, roles=['SYSTEM_UPDATE_WRITE'])
    def set_train(self, train):
        """
        Set an update train to be used by default in updates.
        """
        return self.__set_train(train)

    def __set_train(self, train, trains=None):
        """
        Wrapper so we don't call get_trains twice on update method.
        """
        if trains is None:
            trains = self.get_trains()
        if train != trains['selected']:
            if train not in trains['trains']:
                raise CallError('Invalid train name.', errno.ENOENT)

            try:
                result = compare_trains(trains['current'], train)
            except Exception:
                self.logger.warning(
                    "Failed to compare trains %r and %r", trains['current'], train, exc_info=True
                )
            else:
                if result in BAD_UPGRADES:
                    raise CallError(BAD_UPGRADES[result])

            data = self.middleware.call_sync('datastore.config', 'system.update')
            if data['upd_train'] != train:
                self.middleware.call_sync('datastore.update', 'system.update', data['id'], {
                    'upd_train': train
                })

        return True

    @api_method(UpdateCheckAvailableArgs, UpdateCheckAvailableResult, roles=['SYSTEM_UPDATE_READ'])
    def check_available(self, attrs):
        """
        Checks if there is an update available from update server.

        .. examples(websocket)::

          Check available update using default train:

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "update.check_available"
            }
        """

        try:
            applied = self.middleware.call_sync('cache.get', 'update.applied')
        except KeyError:
            applied = False
        if applied is True:
            return {'status': 'REBOOT_REQUIRED'}

        if self.middleware.call_sync('failover.licensed'):

            # First, let's make sure HA is functional
            if self.middleware.call_sync('failover.disabled.reasons'):
                return {'status': 'HA_UNAVAILABLE'}

            # If its HA and standby is running old version we assume
            # legacy upgrade and check update on standby.
            try:
                self.middleware.call_sync(
                    'failover.call_remote', 'failover.upgrade_version',
                )
            except CallError as e:
                if e.errno != CallError.ENOMETHOD:
                    raise
                return self.middleware.call_sync(
                    'failover.call_remote', 'update.check_available', [attrs],
                )

        trains = self.middleware.call_sync('update.get_trains')
        train = (attrs or {}).get('train')
        if not train:
            train = trains['selected']
        elif train not in trains['trains']:
            raise CallError('Invalid train name.', errno.ENOENT)

        return self.middleware.call_sync('update.check_train', train)

    @api_method(UpdateGetPendingArgs, UpdateGetPendingResult, roles=['SYSTEM_UPDATE_READ'])
    async def get_pending(self, path):
        """
        Gets a list of packages already downloaded and ready to be applied.
        """
        if path is None:
            path = await self.middleware.call('update.get_update_location')

        return await self.middleware.call('update.get_pending_in_path', path)

    @api_method(UpdateUpdateArgs, UpdateUpdateResult, roles=['SYSTEM_UPDATE_WRITE'])
    @job(lock='update')
    @pass_app(rest=True)
    async def update(self, app, job, attrs):
        """
        Downloads (if not already in cache) and apply an update.
        """
        location = await self.middleware.call('update.get_update_location')

        if attrs['resume']:
            options = {'raise_warnings': False}
        else:
            options = {}

            trains = await self.middleware.call('update.get_trains')

            if attrs['train']:
                await self.middleware.run_in_thread(self.__set_train, attrs['train'], trains)
                train = attrs['train']
            else:
                train = trains['selected']

            update = await self.middleware.call('update.download_update', job, train, location, 50)
            if not update:
                raise CallError('No update available')

        await self.middleware.call('update.install', job, os.path.join(location, 'update.sqsh'), options)
        await self.middleware.call('cache.put', 'update.applied', True)
        await self.middleware.call_hook('update.post_update')

        if attrs['reboot']:
            await self.middleware.call('system.reboot', SYSTEM_UPGRADE_REBOOT_REASON, {'delay': 10}, app=app)

        return True

    @api_method(UpdateDownloadArgs, UpdateDownloadResult, roles=['SYSTEM_UPDATE_WRITE'])
    @job(lock='updatedownload')
    def download(self, job):
        """
        Download updates using selected train.
        """
        train = self.middleware.call_sync('update.get_trains')['selected']
        location = self.middleware.call_sync('update.get_update_location')

        return self.middleware.call_sync('update.download_update', job, train, location, 100)

    @private
    async def download_update(self, *args):
        await self.middleware.call('network.general.will_perform_activity', 'update')
        return await self.middleware.call('update.download_impl', *args)

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
                    # We use 90 as max progress here because we will set it to 95 after this completes
                    # in cleanup - otherwise scale build will give 100 and then we will go back to 95
                    'update.install', job, str(update_file.absolute()), options, 90,
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
            if options['cleanup']:
                if unlink_file:
                    if os.path.exists(path):
                        os.unlink(path)

        if path.startswith(UPLOAD_LOCATION):
            self.middleware.call_sync('update.destroy_upload_location')

        self.middleware.call_hook_sync('update.post_update')
        job.set_progress(100, 'Update completed')

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
                # We use 90 as max progress here because we will set it to 95 after this completes
                # in cleanup - otherwise scale build will give 100 and then we will go back to 95
                self.middleware.call_sync('update.install', job, destfile, update_options, 90)
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
        await self.middleware.call_hook('update.post_update')
        job.set_progress(100, 'Update completed')

    @private
    def get_update_location(self):
        syspath = self.middleware.call_sync('systemdataset.config')['path']
        if syspath:
            path = f'{syspath}/update'
        else:
            path = UPLOAD_LOCATION
        os.makedirs(path, exist_ok=True)
        return path


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'update', 'Update')
