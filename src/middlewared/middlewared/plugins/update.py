try:
    from bsd import geom
except ImportError:
    geom = None

from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import job, private, CallError, Service
import middlewared.sqlalchemy as sa

from datetime import datetime
import enum
import errno
import os
import re
import requests
import shutil
import subprocess
import sys
import textwrap

import humanfriendly

try:
    from freenasOS import Configuration, Manifest, Update, Train
    from freenasOS.Exceptions import (
        UpdateIncompleteCacheException, UpdateInvalidCacheException,
        UpdateBusyCacheException,
    )
    from freenasOS.Update import (
        ApplyUpdate, CheckForUpdates, GetServiceDescription, ExtractFrozenUpdate,
    )
except ImportError:
    freenasOS = None

UPLOAD_LOCATION = '/var/tmp/firmware'
UPLOAD_LABEL = 'updatemdu'


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


class CheckUpdateHandler(object):

    reboot = False

    def __init__(self):
        self.changes = []
        self.restarts = []

    def _pkg_serialize(self, pkg):
        if not pkg:
            return None
        return {
            'name': pkg.Name(),
            'version': pkg.Version(),
            'size': pkg.Size(),
        }

    def call(self, op, newpkg, oldpkg):
        self.changes.append({
            'operation': op,
            'old': self._pkg_serialize(oldpkg),
            'new': self._pkg_serialize(newpkg),
        })

    def diff_call(self, diffs):
        self.reboot = diffs.get('Reboot', False)
        if self.reboot is False:
            # We may have service changes
            for svc in diffs.get("Restart", []):
                self.restarts.append(GetServiceDescription(svc))

    @property
    def output(self):
        output = ''
        for c in self.changes:
            if c['operation'] == 'upgrade':
                output += '%s: %s-%s -> %s-%s\n' % (
                    'Upgrade',
                    c['old']['name'],
                    c['old']['version'],
                    c['new']['name'],
                    c['new']['version'],
                )
            elif c['operation'] == 'install':
                output += '%s: %s-%s\n' % (
                    'Install',
                    c['new']['name'],
                    c['new']['version'],
                )
        for r in self.restarts:
            output += r + "\n"
        return output


class UpdateHandler(object):

    def __init__(self, service, job, download_proportion=50):
        self.service = service
        self.job = job

        self.download_proportion = download_proportion

        self._current_package_index = None
        self._packages_count = None

    def check_handler(self, index, pkg, pkgList):
        self._current_package_index = index - 1
        self._packages_count = len(pkgList)

        pkgname = '%s-%s' % (
            pkg.Name(),
            pkg.Version(),
        )

        self.job.set_progress((self._current_package_index / self._packages_count) * self.download_proportion,
                              'Downloading {}'.format(pkgname))

    def get_handler(
        self, method, filename, size=None, progress=None, download_rate=None
    ):
        if self._current_package_index is None or self._packages_count is None or not progress:
            return

        if size:
            try:
                size = humanfriendly.format_size(int(size))
            except Exception:
                pass

        if download_rate:
            try:
                download_rate = humanfriendly.format_size(int(download_rate)) + "/s"
            except Exception:
                pass

        job_progress = (
            ((self._current_package_index + progress / 100) / self._packages_count) * self.download_proportion)
        filename = filename.rsplit('/', 1)[-1]
        if size and download_rate:
            self.job.set_progress(
                job_progress,
                'Downloading {}: {} ({}%) at {}'.format(
                    filename,
                    size,
                    progress,
                    download_rate,
                )
            )
        else:
            self.job.set_progress(
                job_progress,
                'Downloading {} ({}%)'.format(
                    filename,
                    progress,
                )
            )

    def install_handler(self, index, name, packages):
        total = len(packages)
        self.job.set_progress(
            self.download_proportion + (index / total) * (100 - self.download_proportion),
            'Installing {} ({}/{})'.format(name, index, total),
        )


def get_changelog(train, start='', end=''):
    conf = Configuration.Configuration()
    changelog = conf.GetChangeLog(train=train)
    if not changelog:
        return None
    return parse_changelog(changelog.read().decode('utf8', 'ignore'), start, end)


def parse_changelog(changelog, start='', end=''):
    regexp = r'### START (\S+)(.+?)### END \1'
    reg = re.findall(regexp, changelog, re.S | re.M)

    if not reg:
        return None

    changelog = None
    for seq, changes in reg:
        if not changes.strip('\n'):
            continue
        if seq == start:
            # Once we found the right one, we start accumulating
            changelog = ''
        elif changelog is not None:
            changelog += changes.strip('\n') + '\n'
        if seq == end:
            break

    return changelog


class UpdateModel(sa.Model):
    __tablename__ = 'system_update'

    id = sa.Column(sa.Integer(), primary_key=True)
    upd_autocheck = sa.Column(sa.Boolean(), default=True)
    upd_train = sa.Column(sa.String(50))


class UpdateService(Service):

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

    def _get_redir_trains(self):
        """
        The expect trains redirection JSON format is the following:

        {
            "SOURCE_TRAIN_NAME": {
                "redirect": "NAME_NEW_TRAIN"
            }
        }

        The format uses an dict/object as the value to allow new items to be added in the future
        and be backward compatible.
        """
        update_server = Configuration.Configuration().UpdateServerMaster()
        r = requests.get(
            f'{update_server}/trains_redir.json',
            timeout=5,
        )
        rv = {}
        for k, v in r.json().items():
            rv[k] = v['redirect']
        return rv

    @accepts()
    def get_trains(self):
        """
        Returns available trains dict and the currently configured train as well as the
        train of currently booted environment.
        """
        data = self.middleware.call_sync('datastore.config', 'system.update')
        conf = Configuration.Configuration()
        conf.LoadTrainsConfig()

        try:
            redir_trains = self._get_redir_trains()
        except Exception:
            self.logger.warn('Failed to retrieve trains redirection', exc_info=True)
            redir_trains = {}

        selected = None
        trains = {}
        for name, descr in (conf.AvailableTrains() or {}).items():
            train = conf._trains.get(name)
            if train is None:
                train = Train.Train(name, descr)

            try:
                result = compare_trains(conf.CurrentTrain(), train.Name())
            except Exception:
                self.logger.warning(
                    "Failed to compare trains %r and %r", conf.CurrentTrain(), train.Name(), exc_info=True
                )
                continue
            else:
                if result in BAD_UPGRADES:
                    continue

            if not selected and data['upd_train'] == train.Name():
                selected = data['upd_train']
            if name in redir_trains:
                continue
            trains[train.Name()] = {
                'description': descr,
                'sequence': train.LastSequence(),
            }
        if not data['upd_train'] or not selected:
            selected = conf.CurrentTrain()

        if selected in redir_trains:
            selected = redir_trains[selected]
        return {
            'trains': trains,
            'current': conf.CurrentTrain(),
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
    def check_available(self, attrs=None):
        """
        Checks if there is an update available from update server.

        status:
          - REBOOT_REQUIRED: an update has already been applied
          - AVAILABLE: an update is available
          - UNAVAILABLE: no update available

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

        if (
            not self.middleware.call_sync('system.is_freenas') and
            self.middleware.call_sync('failover.licensed')
        ):
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

        handler = CheckUpdateHandler()
        manifest = CheckForUpdates(
            diff_handler=handler.diff_call,
            handler=handler.call,
            train=train,
        )

        if not manifest:
            return {'status': 'UNAVAILABLE'}

        data = {
            'status': 'AVAILABLE',
            'changes': handler.changes,
            'notice': manifest.Notice(),
            'notes': manifest.Notes(),
        }

        conf = Configuration.Configuration()
        sys_mani = conf.SystemManifest()
        if sys_mani:
            sequence = sys_mani.Sequence()
        else:
            sequence = ''
        data['changelog'] = get_changelog(
            train,
            start=sequence,
            end=manifest.Sequence()
        )

        data['version'] = manifest.Version()
        return data

    @accepts(Str('path', null=True, default=None))
    async def get_pending(self, path=None):
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
        data = []
        try:
            changes = await self.middleware.run_in_thread(Update.PendingUpdatesChanges, path)
        except (
            UpdateIncompleteCacheException, UpdateInvalidCacheException,
            UpdateBusyCacheException,
        ):
            changes = []
        if changes:
            if changes.get("Reboot", True) is False:
                for svc in changes.get("Restart", []):
                    data.append({
                        'operation': svc,
                        'name': Update.GetServiceDescription(svc),
                    })
            for new, op, old in changes['Packages']:
                if op == 'upgrade':
                    name = '%s-%s -> %s-%s' % (
                        old.Name(),
                        old.Version(),
                        new.Name(),
                        new.Version(),
                    )
                elif op == 'install':
                    name = '%s-%s' % (new.Name(), new.Version())
                else:
                    # Its unclear why "delete" would feel out new
                    # instead of old, sounds like a pkgtools bug?
                    if old:
                        name = '%s-%s' % (old.Name(), old.Version())
                    else:
                        name = '%s-%s' % (new.Name(), new.Version())

                data.append({
                    'operation': op,
                    'name': name,
                })
        return data

    @accepts(Dict(
        'update',
        Str('train', required=False),
        Bool('reboot', default=False),
        required=False,
    ))
    @job(lock='update', process=True)
    async def update(self, job, attrs=None):
        """
        Downloads (if not already in cache) and apply an update.
        """
        attrs = attrs or {}

        trains = await self.middleware.call('update.get_trains')
        train = attrs.get('train') or trains['selected']

        if attrs.get('train'):
            await self.middleware.run_in_thread(self.__set_train, attrs.get('train'), trains)

        location = await self.middleware.call('update.get_update_location')

        job.set_progress(0, 'Retrieving update manifest')

        handler = UpdateHandler(self, job)

        update = Update.DownloadUpdate(
            train,
            location,
            check_handler=handler.check_handler,
            get_handler=handler.get_handler,
        )
        if update is False:
            raise ValueError('No update available')

        new_manifest = Manifest.Manifest(require_signature=True)
        new_manifest.LoadPath('{}/MANIFEST'.format(location))

        Update.ApplyUpdate(
            location,
            install_handler=handler.install_handler,
        )
        await self.middleware.call('cache.put', 'update.applied', True)

        if (
            await self.middleware.call('system.is_freenas') or
            (
                await self.middleware.call('failover.licensed') and
                await self.middleware.call('failover.status') != 'BACKUP'
            )
        ):
            await self.middleware.call('update.take_systemdataset_samba4_snapshot')

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

        job.set_progress(0, 'Retrieving update manifest')

        handler = UpdateHandler(self, job, 100)

        Update.DownloadUpdate(
            train,
            location,
            check_handler=handler.check_handler,
            get_handler=handler.get_handler,
        )
        update = Update.CheckForUpdates(train=train, cache_dir=location)

        self.middleware.call_sync('alert.alert_source_clear_run', 'HasUpdate')

        return bool(update)

    @accepts(Str('path'))
    @job(lock='updatemanual', process=True)
    def manual(self, job, path):
        """
        Apply manual update of file `path`.
        """
        dest_extracted = os.path.join(os.path.dirname(path), '.update')
        try:
            try:
                job.set_progress(30, 'Extracting file')
                ExtractFrozenUpdate(path, dest_extracted, verbose=True)
                job.set_progress(50, 'Applying update')
                ApplyUpdate(dest_extracted)
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
                dest = '/var/tmp/firmware'
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

            def do_update():
                try:
                    job.set_progress(30, 'Extracting uploaded file')
                    ExtractFrozenUpdate(destfile, dest_extracted, verbose=True)
                    job.set_progress(50, 'Applying update')
                    if ApplyUpdate(dest_extracted) is None:
                        raise ValueError('Uploaded file is not a manual update file')
                except Exception as e:
                    raise CallError(str(e))

            await self.middleware.run_in_thread(do_update)

            job.set_progress(95, 'Cleaning up')

        finally:
            if os.path.exists(destfile):
                os.unlink(destfile)

            if os.path.exists(dest_extracted):
                shutil.rmtree(dest_extracted, ignore_errors=True)

        if dest == '/var/tmp/firmware':
            await self.middleware.call('update.destroy_upload_location')

        job.set_progress(100, 'Update completed')

    @private
    async def get_update_location(self):
        syspath = (await self.middleware.call('systemdataset.config'))['path']
        if syspath:
            return f'{syspath}/update'
        return UPLOAD_LOCATION

    @private
    def create_upload_location(self):
        geom.scan()
        klass_label = geom.class_by_name('LABEL')
        prov = klass_label.xml.find(
            f'.//provider[name = "label/{UPLOAD_LABEL}"]/../consumer/provider'
        )
        if prov is None:
            cp = subprocess.run(
                ['mdconfig', '-a', '-t', 'swap', '-s', '2800m'],
                text=True, capture_output=True, check=False,
            )
            if cp.returncode != 0:
                raise CallError(f'Could not create memory device: {cp.stderr}')
            mddev = cp.stdout.strip()

            subprocess.run(['glabel', 'create', UPLOAD_LABEL, mddev], capture_output=True, check=False)

            cp = subprocess.run(
                ['newfs', f'/dev/label/{UPLOAD_LABEL}'],
                text=True, capture_output=True, check=False,
            )
            if cp.returncode != 0:
                raise CallError(f'Could not create temporary filesystem: {cp.stderr}')

            shutil.rmtree(UPLOAD_LOCATION, ignore_errors=True)
            os.makedirs(UPLOAD_LOCATION)

            cp = subprocess.run(
                ['mount', f'/dev/label/{UPLOAD_LABEL}', UPLOAD_LOCATION],
                text=True, capture_output=True, check=False,
            )
            if cp.returncode != 0:
                raise CallError(f'Could not mount temporary filesystem: {cp.stderr}')

        shutil.chown(UPLOAD_LOCATION, 'www', 'www')
        os.chmod(UPLOAD_LOCATION, 0o755)
        return UPLOAD_LOCATION

    @private
    def destroy_upload_location(self):
        geom.scan()
        klass_label = geom.class_by_name('LABEL')
        prov = klass_label.xml.find(
            f'.//provider[name = "label/{UPLOAD_LABEL}"]/../consumer/provider'
        )
        if prov is None:
            return
        klass_md = geom.class_by_name('MD')
        prov = klass_md.xml.find(f'.//provider[@id = "{prov.attrib["ref"]}"]/name')
        if prov is None:
            return

        mddev = prov.text

        subprocess.run(
            ['umount', f'/dev/label/{UPLOAD_LABEL}'], capture_output=True, check=False,
        )
        cp = subprocess.run(
            ['mdconfig', '-d', '-u', mddev],
            text=True, capture_output=True, check=False,
        )
        if cp.returncode != 0:
            raise CallError(f'Could not destroy memory device: {cp.stderr}')

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

        current_version = "-".join(self.middleware.call_sync("system.info")["version"].split("-")[1:])
        snapshot = f'update--{datetime.utcnow().strftime("%Y-%m-%d-%H-%M")}--{current_version}'
        subprocess.run(['zfs', 'snapshot', f'{dataset}@{snapshot}'])
