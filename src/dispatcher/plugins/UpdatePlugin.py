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
import sys
import re
import gettext
from cache import CacheStore
from task import (Provider, Task, ProgressTask, TaskException, VerifyException)
from dispatcher.rpc import (RpcException, description, accepts, TaskException,
                            returns, SchemaHelper as h)
from lib.system import system

sys.path.append('/usr/local/lib')
from freenasOS import Configuration
from freenasOS.Exceptions import UpdateManifestNotFound
from freenasOS.Update import (
    ActivateClone, CheckForUpdates, DeleteClone, PendingUpdates,
    PendingUpdatesChanges, DownloadUpdate, ApplyUpdate
)

# TODO: Will the below translation func work?
t = gettext.translation('freenas-dispatcher', fallback=True)
_ = t.ugettext

update_cache = CacheStore()


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
        output = []
        for c in self.changes:
            opdict = {
                'operation': c['operation'],
                'prevName': c['old'].Name(),
                'prevVer': c['old'].Version(),
                'newName': c['new'].Name(),
                'newVer': c['new'].Version()
            }
            output.append(opdict)
        return output


@description("A handler for Downloading and Applying Updates calls")
class UpdateHandler(object):

    def __init__(self, apply_=None):
        self.apply = apply_
        self.details = ''
        self.indeterminate = False
        self.progress = 0
        self.step = 1
        self.finished = False
        self.error = False
        self.reboot = False
        self.pkgname = ''
        self.pkgversion = ''
        self.operation = ''
        self.filename = ''
        self.filesize = 0
        self.numfilestotal = 0
        self.numfilesdone = 0
        self._baseprogress = 0

    def check_handler(self, index, pkg, pkgList):
        self.step = 1
        self.pkgname = pkg.Name()
        self.pkgversion = pkg.Version()
        self.operation = _('Downloading')
        self.details = '%s %s' % (
            _('Downloading'),
            '%s-%s' % (self.pkgname, self.pkgversion),
        )
        stepprogress = int((1.0 / float(len(pkgList))) * 100)
        self._baseprogress = index * stepprogress
        self.progress = (index - 1) * stepprogress
        self.emit_uptate_details()

    def get_handler(
        self, method, filename, size=None, progress=None, download_rate=None
    ):
        filename = filename.rsplit('/', 1)[-1]
        if progress is not None:
            self.progress = (progress * self._baseprogress) / 100
            if self.progress == 0:
                self.progress = 1
            self.details = '%s %s(%d%%)%s' % (
                filename,
                '%s ' % size
                if size else '',
                progress,
                '  %s/s' % download_rate
                if download_rate else '',
            )
        self.emit_uptate_details()

    def install_handler(self, index, name, packages):
        if self.apply:
            self.step = 2
        else:
            self.step = 1
        self.indeterminate = False
        total = len(packages)
        self.numfilesdone = index
        self.numfilesdone = total
        self.progress = int((float(index) / float(total)) * 100.0)
        self.operation = _('Installing')
        self.details = '%s %s (%d/%d)' % (
            _('Installing'),
            name,
            index,
            total,
        )

    def emit_uptate_details(self):
        data = {
            'apply': self.apply,
            'error': self.error,
            'operation': self.operation,
            'finished': self.finished,
            'indeterminate': self.indeterminate,
            'percent': self.progress,
            'step': self.step,
            'reboot': self.reboot,
            'pkgName': self.pkgname,
            'pkgVersion': self.pkgversion,
            'filename': self.filename,
            'filesize': self.filesize,
            'numFilesDone': self.numfilesdone,
            'numFilesTotal': self.numfilestotal,
        }
        if self.details:
            data['details'] = self.details
        # TODO: add actual dispatcher event emit code


def generate_update_cache(dispatcher):
    try:
        cache_dir 
    dispatcher.rpc.call_sync('system-dataset.request_directory',
                             'freenas_update')
    # update_cache.put()
    pass


@description("Provides System Updater Configuration")
class UpdateProvider(Provider):

    @returns(str)
    def is_update_availabe(self):
        temp_updateAvailable = update_cache.get('updateAvailable',
                                                timeout=1)
        if temp_updateAvailable is not None:
            return temp_updateAvailable
        elif update_cache.is_valid('updateAvailable'):
            return temp_updateAvailable
        else:
            raise RpcException(
                errno.EBUSY,
                'Update Availability flag is invalidated, an Update Check' +
                ' might be underway. Try again in some time.')

    # TODO: Change to array of strings instead of one gigantic string
    @returns(str)
    def get_changelog(self):
        temp_changelog = update_cache.get('changelog', timeout=1)
        if temp_changelog is not None:
            return temp_changelog
        elif update_cache.is_valid('changelog'):
            return temp_changelog
        else:
            raise RpcException(
                errno.EBUSY,
                'Changelog list is invalidated, an Update Check' +
                ' might be underway. Try again in some time.')

    # TODO: dont be lazy and write the schema for this
    def get_update_ops(self):
        temp_updateOperations = update_cache.get('updateOperations', timeout=1)
        if temp_updateOperations is not None:
            return temp_updateOperations
        elif update_cache.is_valid('updateOperations'):
            return temp_updateOperations
        else:
            raise RpcException(
                errno.EBUSY,
                'Update Operations Dict is invalidated, an Update Check' +
                ' might be underway. Try again in some time.')

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
        return []

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
        return []

    def run(self):
        update_cache.invalidate('updateAvailable')
        update_cache.invalidate('updateOperations')
        update_cache.invalidate('changelog')
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
        except UpdateManifestNotFound:
            update_cache.put('updateAvailable', False)
            update_cache.put('updateOperations', update_ops)
            update_cache.put('changelog', '')
            TaskException(errno.ENETUNREACH,
                          'Update server could not be reached')

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
        update_cache.put('updateAvailable', True if update else False)
        update_cache.put('updateOperations', update_ops)
        update_cache.put('changelog', changelog)


@description("Downloads Updates for the current system update train")
@accepts()
class DownloadUpdateTask(ProgressTask):
    def describe(self):
        return "Downloads the Updates and caches them to apply when needed"

    def verify(self):
        # TODO: Fix this verify's resource allocation as unique task
        return []

    def run(self):
        self.progress = 0
        self.message = 'Downloading Updates...'
        train = self.dispatcher.configstore.get('update.train')
        # To be continued ...


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

    # Get the Update Cache (if any) at system boot (and hence in init here)
    generate_update_cache(dispatcher)
