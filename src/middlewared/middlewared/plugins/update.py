from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import job, CallError, Service

import errno
import os
import re
import shutil
import sys

if '/usr/local/lib' not in sys.path:
    sys.path.append('/usr/local/lib')

import humanfriendly

from freenasOS import Configuration, Manifest, Update, Train
from freenasOS.Exceptions import (
    UpdateIncompleteCacheException, UpdateInvalidCacheException,
    UpdateBusyCacheException,
)
from freenasOS.Update import (
    ApplyUpdate, CheckForUpdates, GetServiceDescription, ExtractFrozenUpdate,
)


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


class UpdateService(Service):

    @accepts()
    def get_trains(self):
        """
        Returns available trains dict and the currently configured train as well as the
        train of currently booted environment.
        """
        data = self.middleware.call_sync('datastore.config', 'system.update')
        conf = Configuration.Configuration()
        conf.LoadTrainsConfig()

        selected = None
        trains = {}
        for name, descr in (conf.AvailableTrains() or {}).items():
            train = conf._trains.get(name)
            if train is None:
                train = Train.Train(name, descr)
            if not selected and data['upd_train'] == train.Name():
                selected = data['upd_train']
            trains[train.Name()] = {
                'description': train.Description(),
                'sequence': train.LastSequence(),
            }
        if not data['upd_train'] or not selected:
            selected = conf.CurrentTrain()
        return {
            'trains': trains,
            'current': conf.CurrentTrain(),
            'selected': selected,
        }

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

        train = (attrs or {}).get('train') or self.middleware.call_sync('update.get_trains')['selected']

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
            path = await self.middleware.call('notifier.get_update_location')
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
        train = attrs.get('train') or (await self.middleware.call('update.get_trains'))['selected']
        location = await self.middleware.call('notifier.get_update_location')

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

        if attrs.get('reboot'):
            await self.middleware.call('system.reboot', {'delay': 10})
        return True

    @accepts()
    @job(lock='updatedownload')
    def download(self, job):
        train = self.middleware.call_sync('update.get_trains')['selected']
        location = self.middleware.call_sync('notifier.get_update_location')

        job.set_progress(0, 'Retrieving update manifest')

        handler = UpdateHandler(self, job, 100)

        Update.DownloadUpdate(
            train,
            location,
            check_handler=handler.check_handler,
            get_handler=handler.get_handler,
        )
        update = Update.CheckForUpdates(train=train, cache_dir=location)

        if not update:
            return False

        notified = False
        try:
            if self.middleware.call_sync('cache.has_key', 'update.notified'):
                notified = self.middleware.call_sync('cache.get', 'update.notified')
        except Exception:
            pass

        if not notified:
            self.middleware.call_sync('cache.put', 'update.notified', True)
            conf = Configuration.Configuration()
            sys_mani = conf.SystemManifest()
            if sys_mani:
                sequence = sys_mani.Sequence()
            else:
                sequence = ''

            changelog = get_changelog(train, start=sequence, end=update.Sequence())

            try:
                # FIXME: Translation
                self.middleware.call_sync('mail.send', {
                    'subject': 'Update Available',
                    'text': '''A new update is available for the %(train)s train.
Version: %(version)s
Changelog:
%(changelog)s
''' % {
                        'train': train,
                        'version': update.Version(),
                        'changelog': changelog,
                    },
                }).wait_sync()
            except Exception:
                self.logger.warn('Failed to send email about new update', exc_info=True)
        return True

    @accepts(Str('path'))
    @job(lock='updatemanual', process=True)
    async def manual(self, job, path):
        """
        Apply manual update of file `path`.
        """
        rv = await self.middleware.call('notifier.validate_update', path)
        if not rv:
            raise CallError('Invalid update file', errno.EINVAL)
        await self.middleware.call('notifier.apply_update', path, timeout=None)
        try:
            await self.middleware.call('notifier.destroy_upload_location')
        except Exception:
            self.logger.warn('Failed to destroy upload location', exc_info=True)

    @accepts(Dict(
        'updatefile',
        Str('destination'),
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
                await self.middleware.call('notifier.create_upload_location')
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
                    ApplyUpdate(dest_extracted)
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
            await self.middleware.call('notifier.destroy_upload_location')

        job.set_progress(100, 'Update completed')
