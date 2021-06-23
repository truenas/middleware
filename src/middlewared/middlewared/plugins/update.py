from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import job, private, CallError, Service
import middlewared.sqlalchemy as sa
from middlewared.plugins.update_.utils import UPLOAD_LOCATION

from datetime import datetime
import enum
import errno
import os
import shutil
import subprocess
import textwrap
import pathlib


def parse_train_name(name):
    split = name.split('-')
    version = split[1].split('.')
    branch = split[2]

    return [int(v) if v.isdigit() else v for v in version] + [branch]


class CompareTrainsResult(enum.Enum):
    MAJOR_DOWNGRADE = "MAJOR_DOWNGRADE"
    MAJOR_UPGRADE = "MAJOR_UPGRADE"
    MINOR_DOWNGRADE = "MINOR_DOWNGRADE"
    MINOR_UPGRADE = "MINOR_UPGRADE"
    NIGHTLY_DOWNGRADE = "NIGHTLY_DOWNGRADE"
    NIGHTLY_UPGRADE = "NIGHTLY_UPGRADE"


BAD_UPGRADES = {
    CompareTrainsResult.NIGHTLY_DOWNGRADE: textwrap.dedent("""\
        You're not allowed to change away from the nightly train, it is considered a downgrade.
        If you have an existing boot environment that uses that train, boot into it in order to upgrade
        that train.
    """),
    CompareTrainsResult.MINOR_DOWNGRADE: textwrap.dedent("""\
        Changing minor version is considered a downgrade, thus not a supported operation.
        If you have an existing boot environment that uses that train, boot into it in order to upgrade
        that train.
    """),
    CompareTrainsResult.MAJOR_DOWNGRADE: textwrap.dedent("""\
        Changing major version is considered a downgrade, thus not a supported operation.
        If you have an existing boot environment that uses that train, boot into it in order to upgrade
        that train.
    """),
}


def compare_trains(t1, t2):
    if 'scale' in t1.lower() and 'scale' not in t2.lower():
        return CompareTrainsResult.MAJOR_DOWNGRADE
    if 'scale' not in t1.lower() and 'scale' in t2.lower():
        return CompareTrainsResult.MAJOR_UPGRADE

    v1 = parse_train_name(t1)
    v2 = parse_train_name(t2)

    if v1[0] != v2[0]:
        if v1[0] > v2[0]:
            return CompareTrainsResult.MAJOR_DOWNGRADE
        else:
            return CompareTrainsResult.MAJOR_UPGRADE

    branch1 = v1[-1].lower().replace("-sdk", "")
    branch2 = v2[-1].lower().replace("-sdk", "")
    if branch1 != branch2:
        if branch2 == "nightlies":
            return CompareTrainsResult.NIGHTLY_UPGRADE
        elif branch1 == "nightlies":
            return CompareTrainsResult.NIGHTLY_DOWNGRADE

    if (
        # [11, "STABLE"] -> [11, 1, "STABLE"]
        not isinstance(v1[1], int) and isinstance(v2[1], int) or
        # [11, 1, "STABLE"] -> [11, 2, "STABLE"]
        isinstance(v1[1], int) and isinstance(v2[1], int) and v1[1] < v2[1]
    ):
        return CompareTrainsResult.MINOR_UPGRADE

    if isinstance(v1[1], int):
        if (
            isinstance(v2[1], int) and v1[1] > v2[1] or
            not isinstance(v2[1], int) and v1[1] > 0
        ):
            return CompareTrainsResult.MINOR_DOWNGRADE


class UpdateModel(sa.Model):
    __tablename__ = 'system_update'

    id = sa.Column(sa.Integer(), primary_key=True)
    upd_autocheck = sa.Column(sa.Boolean(), default=True)
    upd_train = sa.Column(sa.String(50))


class UpdateService(Service):

    class Config:
        cli_namespace = 'system.update'

    @accepts()
    async def get_auto_download(self):
        """
        Returns if update auto-download is enabled.
        """
        return (await self.middleware.call('datastore.config', 'system.update'))['upd_autocheck']

    @accepts(Bool('autocheck'))
    async def set_auto_download(self, autocheck):
        """
        Sets if update auto-download is enabled.
        """
        config = await self.middleware.call('datastore.config', 'system.update')
        await self.middleware.call('datastore.update', 'system.update', config['id'], {'upd_autocheck': autocheck})
        await self.middleware.call('service.restart', 'cron')

    @accepts()
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

    @accepts(Str('train', empty=False))
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

    @accepts(Dict(
        'update-check-available',
        Str('train', required=False),
        required=False,
    ))
    def check_available(self, attrs):
        """
        Checks if there is an update available from update server.

        status:
          - REBOOT_REQUIRED: an update has already been applied
          - AVAILABLE: an update is available
          - UNAVAILABLE: no update available
          - HA_UNAVAILABLE: HA is non-functional

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
        except Exception:
            applied = False
        if applied is True:
            return {'status': 'REBOOT_REQUIRED'}

        if self.middleware.call_sync('failover.licensed'):

            # First, let's make sure HA is functional
            if self.middleware.call_sync('failover.disabled_reasons'):
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

    @accepts(Str('path', null=True, default=None))
    async def get_pending(self, path):
        """
        Gets a list of packages already downloaded and ready to be applied.
        Each entry of the lists consists of type of operation and name of it, e.g.

          {
            "operation": "upgrade",
            "name": "baseos-11.0 -> baseos-11.1"
          }
        """
        if path is None:
            path = await self.middleware.call('update.get_update_location')

        return await self.middleware.call('update.get_pending_in_path', path)

    @accepts(Dict(
        'update',
        Str('train', required=False),
        Bool('reboot', default=False),
        required=False,
    ))
    @job(lock='update')
    async def update(self, job, attrs):
        """
        Downloads (if not already in cache) and apply an update.
        """
        trains = await self.middleware.call('update.get_trains')
        train = attrs.get('train') or trains['selected']

        if attrs.get('train'):
            await self.middleware.run_in_thread(self.__set_train, attrs.get('train'), trains)

        location = await self.middleware.call('update.get_update_location')

        update = await self.middleware.call('update.download_update', job, train, location, 50)
        if update is False:
            raise ValueError('No update available')

        await self.middleware.call('update.install_impl', job, location)
        await self.middleware.call('cache.put', 'update.applied', True)
        await self.middleware.call_hook('update.post_update')

        if attrs.get('reboot'):
            await self.middleware.call('system.reboot', {'delay': 10})
        return True

    @accepts()
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
        success = await self.middleware.call('update.download_impl', *args)
        await self.middleware.call('alert.alert_source_clear_run', 'HasUpdate')
        return success

    @accepts(Str('path'))
    @job(lock='updatemanual')
    def manual(self, job, path):
        """
        Update the system using a manual update file.

        `path` must be the absolute path to the update file.
        """

        update_file = pathlib.Path(path)

        # make sure absolute path was given
        if not update_file.is_absolute():
            raise CallError('Absolute path must be provided.', errno.ENOENT)

        # make sure file exists
        if not update_file.exists():
            raise CallError('File does not exist.', errno.ENOENT)

        # dest_extracted is only used on freebsd and ignored on linux
        dest_extracted = os.path.join(str(update_file.parent), '.update')

        try:
            try:
                self.middleware.call_sync(
                    'update.install_manual_impl', job, str(update_file.absolute()), dest_extracted
                )
            except Exception as e:
                self.logger.debug('Applying manual update failed', exc_info=True)
                raise CallError(str(e), errno.EFAULT)

            job.set_progress(95, 'Cleaning up')
        finally:
            if os.path.exists(path):
                os.unlink(path)

            if os.path.exists(dest_extracted):
                shutil.rmtree(dest_extracted, ignore_errors=True)

        if path.startswith(UPLOAD_LOCATION):
            self.middleware.call_sync('update.destroy_upload_location')

        self.middleware.call_hook_sync('update.post_update')

    @accepts(Dict(
        'updatefile',
        Str('destination', null=True),
    ))
    @job(lock='updatemanual', pipes=['input'])
    async def file(self, job, options):
        """
        Updates the system using the uploaded .tar file.

        Use null `destination` to create a temporary location.
        """

        dest = options.get('destination')

        if not dest:
            try:
                await self.middleware.call('update.create_upload_location')
                dest = UPLOAD_LOCATION
            except Exception as e:
                raise CallError(str(e))
        elif not dest.startswith('/mnt/'):
            raise CallError('Destination must reside within a pool')

        if not os.path.isdir(dest):
            raise CallError('Destination is not a directory')

        destfile = os.path.join(dest, 'manualupdate.tar')
        dest_extracted = os.path.join(dest, '.update')

        try:
            job.set_progress(10, 'Writing uploaded file to disk')
            with open(destfile, 'wb') as f:
                await self.middleware.run_in_thread(
                    shutil.copyfileobj, job.pipes.input.r, f, 1048576,
                )

            await self.middleware.call('update.install_manual_impl', job, destfile, dest_extracted)

            job.set_progress(95, 'Cleaning up')
        finally:
            if os.path.exists(destfile):
                os.unlink(destfile)

            if os.path.exists(dest_extracted):
                shutil.rmtree(dest_extracted, ignore_errors=True)

        if dest == UPLOAD_LOCATION:
            await self.middleware.call('update.destroy_upload_location')

        await self.middleware.call_hook('update.post_update')

        job.set_progress(100, 'Update completed')

    @private
    async def get_update_location(self):
        syspath = (await self.middleware.call('systemdataset.config'))['path']
        if syspath:
            path = f'{syspath}/update'
        else:
            path = UPLOAD_LOCATION
        os.makedirs(path, exist_ok=True)
        return path

    @private
    def take_systemdataset_samba4_snapshot(self):
        basename = self.middleware.call_sync('systemdataset.config')['basename']
        if basename is None:
            self.logger.warning('System dataset is not available, not taking snapshot')
            return

        dataset = f'{basename}/samba4'

        proc = subprocess.run(['zfs', 'list', '-t', 'snapshot', '-H', '-o', 'name', '-s', 'name', '-d', '1', dataset],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8', errors='ignore')
        if proc.returncode != 0:
            self.logger.warning('Unable to list dataset %s snapshots: %s', dataset, proc.stderr)
            return

        snapshots = [s.split('@')[1] for s in proc.stdout.strip().split()]
        for snapshot in [s for s in snapshots if s.startswith('update--')][:-4]:
            self.logger.info('Deleting dataset %s snapshot %s', dataset, snapshot)
            subprocess.run(['zfs', 'destroy', f'{dataset}@{snapshot}'])

        current_version = "-".join(self.middleware.call_sync("system.version").split("-")[1:])
        snapshot = f'update--{datetime.utcnow().strftime("%Y-%m-%d-%H-%M")}--{current_version}'
        subprocess.run(['zfs', 'snapshot', f'{dataset}@{snapshot}'])


async def post_update_hook(middleware):
    is_ha = await middleware.call('failover.licensed')
    if not is_ha or await middleware.call('failover.status') != 'BACKUP':
        await middleware.call('update.take_systemdataset_samba4_snapshot')


async def setup(middleware):
    await middleware.call('network.general.register_activity', 'update', 'Update')
    middleware.register_hook('update.post_update', post_update_hook, sync=True)
