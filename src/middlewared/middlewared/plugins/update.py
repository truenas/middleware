from middlewared.schema import accepts, Dict, Str
from middlewared.service import job, Service

import re
import sys

if '/usr/local/lib' not in sys.path:
    sys.path.append('/usr/local/lib')

from freenasOS import Configuration, Manifest, Update
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
    return parse_changelog(changelog.read(), start, end)


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

    def get_train(self):
        """
        Returns currently configured train
        """
        data = self.middleware.call('datastore.config', 'system.update')
        conf = Configuration.Configuration()
        conf.LoadTrainsConfig()
        trains = conf.AvailableTrains() or []
        if trains:
            trains = trains.keys()
        if not data['upd_train'] or data['upd_train'] not in trains:
            return conf.CurrentTrain()

    @accepts(Dict(
        'update-check-available',
        Str('train', required=False),
        required=False,
    ))
    def check_available(self, attrs=None):
        """
        Checks if there is an update available from update server.
        """
        train = (attrs or {}).get('train') or self.get_train()

        handler = CheckUpdateHandler()
        manifest = CheckForUpdates(
            diff_handler=handler.diff_call,
            handler=handler.call,
            train=train,
        )

        data = {
            'changes': handler.changes,
        }

        if not manifest:
            return data

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

    @accepts(Dict(
        'update-check-available',
        Str('train', required=False),
        required=False,
    ))
    @job(lock='update', process=True)
    def update(self, job, attrs=None):
        """
        Downloads (if not already in cache) and apply an update.
        """
        train = (attrs or {}).get('train') or self.get_train()
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
        return True
