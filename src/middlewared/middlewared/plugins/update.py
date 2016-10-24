from middlewared.schema import accepts, Dict, Str
from middlewared.service import Service

import re
import sys

if '/usr/local/lib' not in sys.path:
    sys.path.append('/usr/local/lib')

from freenasOS import Configuration
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
