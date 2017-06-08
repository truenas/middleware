from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import job, Service

import re
import socket
import sys

if '/usr/local/lib' not in sys.path:
    sys.path.append('/usr/local/lib')

from freenasOS import Configuration, Manifest, Update, Train
from freenasOS.Exceptions import (
    UpdateIncompleteCacheException, UpdateInvalidCacheException,
    UpdateBusyCacheException,
)
from freenasOS.Update import CheckForUpdates, GetServiceDescription


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

    def __init__(self, service, job):
        self.service = service
        self.job = job

    def check_handler(self, index, pkg, pkgList):
        pkgname = '%s-%s' % (
            pkg.Name(),
            pkg.Version(),
        )
        step_progress = int((1.0 / len(pkgList)) * 100.0)
        self._baseprogress = index * step_progress

        self.job.set_progress((index - 1) * step_progress, 'Downloading {}'.format(pkgname))

    def get_handler(
        self, method, filename, size=None, progress=None, download_rate=None
    ):
        filename = filename.rsplit('/', 1)[-1]
        if not progress:
            return
        progress = (progress * self._baseprogress) / 100
        if progress == 0:
            progress = 1
        self.job.set_progress(progress, 'Downloading {} {} ({}%) {}/s'.format(
            filename,
            size if size else '',
            progress,
            download_rate if download_rate else '',
        ))

    def install_handler(self, index, name, packages):
        total = len(packages)
        self.job.set_progress(
            int((float(index) / float(total)) * 100.0),
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
        data = self.middleware.call('datastore.config', 'system.update')
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
            applied = self.middleware.call('cache.get', 'update.applied')
        except Exception:
            applied = False
        if applied is True:
            return {'status': 'REBOOT_REQUIRED'}

        train = (attrs or {}).get('train') or self.get_trains()['selected']

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

    @accepts(Str('path'))
    def get_pending(self, path=None):
        """
        Gets a list of packages already downloaded and ready to be applied.
        Each entry of the lists consists of type of operation and name of it, e.g.

          {
            "operation": "upgrade",
            "name": "baseos-11.0 -> baseos-11.1"
          }
        """
        if path is None:
            path = self.middleware.call('notifier.get_update_location')
        data = []
        try:
            changes = self.middleware.threaded(Update.PendingUpdatesChanges, path)
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
    def update(self, job, attrs=None):
        """
        Downloads (if not already in cache) and apply an update.
        """
        train = (attrs or {}).get('train') or self.get_trains()['selected']
        location = self.middleware.call('notifier.get_update_location')

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
        self.middleware.call('cache.put', 'update.applied', True)

        if attrs.get('reboot'):
            self.middleware.call('system.reboot', {'delay': 10})
        return True

    @accepts()
    @job(lock='updatedownload', process=True)
    def download(self, job):
        train = self.get_trains()['selected']
        location = self.middleware.call('notifier.get_update_location')

        Update.DownloadUpdate(
            train,
            location,
        )
        update = Update.CheckForUpdates(train=train, cache_dir=location)

        if not update:
            return False

        notified = False
        try:
            if self.middleware.call('cache.has_key', 'update.notified'):
                notified = self.middleware.call('cache.get', 'update.notified')
        except Exception:
            pass

        if not notified:
            self.middleware.call('cache.put', 'update.notified', True)
            conf = Configuration.Configuration()
            sys_mani = conf.SystemManifest()
            if sys_mani:
                sequence = sys_mani.Sequence()
            else:
                sequence = ''

            changelog = get_changelog(train, start=sequence, end=update.Sequence())
            hostname = socket.gethostname()

            try:
                # FIXME: Translation
                self.middleware.call('mail.send', {
                    'subject': '{}: {}'.format(hostname, 'Update Available'),
                    'text': '''A new update is available for the %(train)s train.
Version: %(version)s
Changelog:
%(changelog)s
''' % {
                        'train': train,
                        'version': update.Version(),
                        'changelog': changelog,
                    },
                })
            except Exception:
                self.logger.warn('Failed to send email about new update', exc_info=True)
        return True
