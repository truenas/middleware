# -*- coding=utf-8 -*-
import re

import requests

from freenasOS import Configuration, Train
from freenasOS.Update import CheckForUpdates, GetServiceDescription

from middlewared.service import private, Service


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
    @private
    def get_trains_data(self):
        try:
            redir_trains = self._get_redir_trains()
        except Exception:
            self.logger.warn('Failed to retrieve trains redirection', exc_info=True)
            redir_trains = {}

        conf = Configuration.Configuration()
        conf.LoadTrainsConfig()

        trains = {}
        for name, descr in (conf.AvailableTrains() or {}).items():
            train = conf._trains.get(name)
            if train is None:
                train = Train.Train(name, descr)

            trains[train.Name()] = {
                'description': descr,
                'sequence': train.LastSequence(),
            }

        scale_trains = self.middleware.call_sync('update.get_scale_trains_data')
        trains.update(**scale_trains['trains'])

        return {
            'trains': trains,
            'current_train': conf.CurrentTrain(),
            'trains_redirection': redir_trains,
        }

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
        r = requests.get(
            f'{Configuration.Configuration().UpdateServerMaster()}/trains_redir.json',
            timeout=5,
        )
        rv = {}
        for k, v in r.json().items():
            rv[k] = v['redirect']
        return rv

    @private
    def check_train(self, train):
        if 'SCALE' in train:
            old_version = self.middleware.call_sync('system.version').split('-', 1)[1]
            return self.middleware.call_sync('update.get_scale_update', train, old_version)

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
