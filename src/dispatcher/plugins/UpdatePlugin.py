# +
# Copyright 2014 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

import errno
import os
import sys
import re
from task import (Provider, Task, ProgressTask, TaskException, VerifyException)
from dispatcher.rpc import (RpcException, description, accepts,
                            returns, SchemaHelper as h)
from lib.system import system

sys.path.append('/usr/local/lib')
from freenasOS import Configuration
from freenasOS.Exceptions import UpdateManifestNotFound
from freenasOS.Update import (
    ActivateClone,
    CheckForUpdates,
    DeleteClone,
)


@description("Utility function to parse an available changelog")
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


@description("Utility to get and eventually parse a changelog if available")
def get_changelog(train, start='', end=''):
    conf = Configuration.Configuration()
    changelog = conf.GetChangeLog(train=train)
    if not changelog:
        return None

    return parse_changelog(changelog.read(), start, end)


# The handler(s) below is/are taken from the freenas 9.3 code
# specifically from gui/system/utils.py
@description("A handler for the CheckUpdate call")
class CheckUpdateHandler(object):

    def __init__(self):
        self.changes = []

    def call(self, op, newpkg, oldpkg):
        self.changes.append({
            'operation': op,
            'old': oldpkg,
            'new': newpkg,
        })

    def output(self):
        output = None
        for c in self.changes:
            opdict = {
                'operation': c['operation'],
                'prev_name': c['old'].Name(),
                'prev_ver': c['old'].Version(),
                'new_name': c['new'].Name(),
                'new_ver': c['new'].Version()
            }
            output.append(opdict)
        return output


@description("Provides System Updater Configuration")
class UpdateProvider(Provider):

    @returns(str)
    def get_current_train(self):
        return self.dispatcher.configstore.get('update.train')

    @returns(h.ref('update'))
    def get_config(self):
        return {
            'train': self.dispatcher.configstore.get('update.train'),
            'updateCheckAuto': self.dispatcher.configstore.get(
                'update.check_auto'),
        }


@description("Set the System Updater Cofiguration Settings")
@accepts(h.ref('update'))
class UpdateConfigureTask(Task):

    def describe(self):
        return "System Updater Configure Settings"

    def verify(self, props):
        # TODO: Fix this verify's resource allocation as unique task
        train_to_set = props.get('train')
        conf = Configuration.Configuration()
        conf.LoadTrainsConfig()
        trains = conf.AvailableTrains() or []
        if trains:
            trains = trains.keys()
        if train_to_set not in trains:
            raise VerifyException(
                errno.ENOENT,
                '{0} is not a valid train'.format(train_to_set))
        return ['']

    def run(self, props):
        self.dispatcher.configstore.set(
            'update.train',
            props.get('train'),
        )
        self.dispatcher.configstore.set(
            'update.check_auto',
            props.get('updateCheckAuto'),
        )
        self.dispatcher.dispatch_event('update.changed', {
            'operation': 'update',
            'ids': ['update'],
        })


@description("Checks for Available Updates and returns if update is availabe" +
             " and if yes returns information on operations that will be" +
             " performed during the update")
@accepts()
class CheckUpdateTask(Task):
    def describe(self):
        return "Checks for Updates and Reports Operations to be performed"

    def verify(self):
        # TODO: Fix this verify's resource allocation as unique task
        return ['']

    def run(self):
        conf = Configuration.Configuration()
        update_ops = None
        handler = CheckUpdateHandler()
        # Fix get_current_train() with datastore object of user specified train
        train = self.dispatcher.configstore.get('update.train')
        try:
            update = CheckForUpdates(
                handler=handler.call,
                train=train,
            )
            network = True
        except UpdateManifestNotFound:
            update = False
            network = False
        if update:
            update_ops = handler.output()
            sys_mani = conf.SystemManifest()
            if sys_mani:
                sequence = sys_mani.Sequence()
            else:
                sequence = ''
            changelog = get_changelog(train,
                                      start=sequence,
                                      end=update.Sequence())
        else:
            changelog = None
        return {
            'updateAvailable': True if update else False,
            'network': network,
            'updateOperations': update_ops,
            'changelog': changelog,
        }


@description("Downloads Updates for the current system update train")
@accepts()
class DownloadUpdateTask(ProgressTask):
    def describe(self):
        return "Downloads the Updates and caches them to apply when needed"

    def verify(self):
        # TODO: Fix this verify's resource allocation as unique task
        return ['']

    def run(self):
        self.progress = 0
        self.message = 'Executing...'
        # Fix cache_dir with either this or "sys_dataset_path/update" path
        cache_dir = '/var/tmp/update'
        train = self.dispatcher.configstore.get('update.train')
        # To be continued after discussion with Sef




# Fix this when the fn10 freenas-pkg tools is updated by sef
@description("Runs a ghetto `freenas-update update`")
class UpdateTask(Task):
    def describe(self):
        return "FreeNAS Update"

    def verify(self):
        return ['root']

    def run(self):
        try:
            self.dispatcher.dispatch_event('update.changed', {
                'operation': 'started',
            })
            system('/usr/local/bin/freenas-update', 'update')
            self.run_subtask('system.reboot')
        except Exception as e:
            raise TaskException(errno.EAGAIN,
                                'Update Process Failed! Reason: %s' % e)


def _init(dispatcher, plugin):
    # Register Schemas
    plugin.register_schema_definition('update', {
        'type': 'object',
        'properties': {
            'train': {'type': 'string'},
            'updateCheckAuto': {'type': 'boolean'},
        },
    })
    # Register providers
    plugin.register_provider("update", UpdateProvider)

    # Register task handlers
    plugin.register_task_handler("update.configure", UpdateConfigureTask)
    plugin.register_task_handler("update.check", CheckUpdateTask)
    plugin.register_task_handler("update.download", DownloadUpdateTask)
    plugin.register_task_handler("update.update", UpdateTask)
