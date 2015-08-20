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
import json
import logging
import os
import re
from uuid import uuid4

from django.utils.translation import ugettext as _
from lockfile import LockFile

from freenasOS import Update
from freenasUI.common.pipesubr import pipeopen

log = logging.getLogger('system.utils')


class BootEnv(object):

    def __init__(
            self, id=None, active=None, on_reboot=None, mountpoint=None, space=None, created=None, **kwargs
    ):
        self._id = id
        self.active = active
        self.on_reboot = on_reboot
        self.created = created
        self.mountpoint = mountpoint
        self.name = id
        self.space = space

    @property
    def id(self):
        return self._id


class CheckUpdateHandler(object):

    reboot = False

    def __init__(self):
        self.changes = []
        self.restarts = []

    def call(self, op, newpkg, oldpkg):
        self.changes.append({
            'operation': op,
            'old': oldpkg,
            'new': newpkg,
        })

    def diff_call(self, diffs):
        self.reboot = diffs.get('Reboot', False)
        if self.reboot is False:
            from freenasOS.Update import GetServiceDescription
            # We may have service changes
            for svc in diffs.get("Restart", []):
                self.restarts.append(GetServiceDescription(svc))

    @property
    def output(self):
        output = ''
        for c in self.changes:
            if c['operation'] == 'upgrade':
                output += '%s: %s-%s -> %s-%s\n' % (
                    _('Upgrade'),
                    c['old'].Name(),
                    c['old'].Version(),
                    c['new'].Name(),
                    c['new'].Version(),
                )
            elif c['operation'] == 'install':
                output += '%s: %s-%s\n' % (
                    _('Install'),
                    c['new'].Name(),
                    c['new'].Version(),
                )
        for r in self.restarts:
            output += r + "\n"
        return output


def task_running(request):
    from freenasUI.middleware.connector import connection as dispatcher
    tid = request.session.get('update', {}).get('task')
    if tid is None:
        return False, None
    task = dispatcher.call_sync('task.status', int(tid))
    if task is None:
        return False, None
    if task['state'] in ('FINISHED', 'FAILED'):
        return False, task
    return True, task


class VerifyHandler(object):

    DUMPFILE = '/tmp/.verifyprogress'

    def __init__(self, correct_=None):
        if os.path.exists(self.DUMPFILE):
            self.load()
        else:
            self.details = ''
            self.indeterminate = False
            self.progress = 0
            self.step = 1
            self.finished = False
            self.error = False
            self.mode = "single"

    def verify_handler(self, index, total, fname):
        self.step = 1
        self.details = '%s %s' % (
            _('Verifying'),
            fname,
        )
        self.progress = int((float(index) / float(total)) * 100.0)
        self.dump()

    def dump(self):
        with LockFile(self.DUMPFILE) as lock:
            with open(self.DUMPFILE, 'wb') as f:
                data = {
                    'error': self.error,
                    'finished': self.finished,
                    'indeterminate': self.indeterminate,
                    'percent': self.progress,
                    'step': self.step,
                    'mode': self.mode,
                }
                if self.details:
                    data['details'] = self.details
                f.write(json.dumps(data))

    def load(self):
        if not os.path.exists(self.DUMPFILE):
            return None
        with LockFile(self.DUMPFILE) as lock:
            with open(self.DUMPFILE, 'rb') as f:
                data = json.loads(f.read())
        self.details = data.get('details', '')
        self.error = data['error']
        self.finished = data['finished']
        self.indeterminate = data['indeterminate']
        self.progress = data['percent']
        self.mode = data['mode']
        self.step = data['step']
        return data

    def exit(self):
        log.debug("VerifyUpdate: handler.exit() was called")
        if os.path.exists(self.DUMPFILE):
            os.unlink(self.DUMPFILE)


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


def get_pending_updates(path):
    data = []
    changes = Update.PendingUpdatesChanges(path)
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
                name = '%s-%s' % (old.Name(), old.Version())

            data.append({
                'operation': op,
                'name': name,
            })
    return data


def manual_update(path, sha256):
    from freenasUI.middleware.notifier import notifier
    from freenasUI.middleware.exceptions import MiddlewareError

    # Verify integrity of uploaded image.
    checksum = notifier().checksum(path)
    if checksum != sha256.lower().strip():
        raise MiddlewareError("Invalid update file, wrong checksum")

    # Validate that the image would pass all pre-install
    # requirements.
    #
    # IMPORTANT: pre-install step have scripts or executables
    # from the upload, so the integrity has to be verified
    # before we proceed with this step.
    retval = notifier().validate_update(path)

    if not retval:
        raise MiddlewareError("Invalid update file")

    notifier().apply_update(path)
    try:
        notifier().destroy_upload_location()
    except Exception, e:
        log.warn("Failed to destroy upload location: %s", e.value)


def debug_get_settings():
    from freenasUI.middleware.notifier import notifier
    direc = "/var/tmp/ixdiagnose"
    mntpt = '/var/tmp'
    if notifier().system_dataset_path() is not None:
        direc = os.path.join(notifier().system_dataset_path(), 'ixdiagnose')
        mntpt = notifier().system_dataset_path()
    dump = os.path.join(direc, 'ixdiagnose.tgz')

    return (mntpt, direc, dump)


def debug_run(direc):
    # Be extra safe in case we have left over from previous run
    if os.path.exists(direc):
        opts = ["/bin/rm", "-r", "-f", direc]
        p1 = pipeopen(' '.join(opts), allowfork=True)
        p1.wait()

    opts = ["/usr/local/bin/ixdiagnose", "-d", direc, "-s", "-F"]
    p1 = pipeopen(' '.join(opts), allowfork=True)
    p1.communicate()
