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
import tarfile
import signal

from uuid import uuid4

from django.contrib.auth import login, get_backends
from django.utils.translation import ugettext as _
from lockfile import LockFile

from freenasOS import Update
from freenasUI.common import humanize_size
from freenasUI.common.pipesubr import pipeopen

log = logging.getLogger('system.utils')

UPDATE_APPLIED_SENTINEL = '/tmp/.updateapplied'


def is_update_applied(update_version, create_alert=True):
    active_be_msg = 'Please Reboot the system to avail of this update'
    # TODO: The below boot env name should really be obtained from the update code
    # for now we just duplicate that code here
    if update_version.startswith(Update.Avatar() + "-"):
        update_boot_env = update_version[len(Update.Avatar() + "-"):]
    else:
        update_boot_env = "%s-%s" % (Update.Avatar(), update_version)

    found = False
    msg = ''
    for clone in Update.ListClones():
        if clone['realname'] == update_boot_env:
            if clone['active'] != 'R':
                active_be_msg = 'Please activate {0} via'.format(update_boot_env) + \
                                ' the Boot Environment Tab and Reboot to use this updated version'
            msg = 'Update: {0} has already been applied. {1}'.format(update_version, active_be_msg)
            found = True
            if create_alert:
                create_update_alert(update_version)
            break

    return (found, msg)


def create_update_alert(update_version):
    # Create Alert that update is applied and system should now be
    # rebooted. This is to catch the corner case when the update.py
    # daemon errors out AFTER an update was applied and its BootEnv
    # created (and sometimes even activated)
    with open(UPDATE_APPLIED_SENTINEL, 'wb+') as f:
        f.write(json.dumps({'update_version': update_version}))
    # Now send SIGUSR1 (signal 10) to the alertd daemon (to rescan
    # alertmods)
    try:
        with open("/var/run/alertd.pid", "r") as f:
            alertd_pid = int(f.read())
        os.kill(alertd_pid, signal.SIGUSR1)
    except:
        # alertd not running?
        pass


class BootEnv(object):

    def __init__(
            self, name=None, active=None, mountpoint=None, space=None, created=None, keep=None, **kwargs
    ):
        self._id = name
        self.active = active
        self._created = created
        self.mountpoint = mountpoint
        self.name = name
        self.keep = keep
        self.space = space

    @property
    def id(self):
        return self._id

    @property
    def created(self):
        return self._created.strftime('%Y-%m-%d %H:%M:%S')


class UpdateHandler(object):

    DUMPFILE = '/tmp/.upgradeprogress'

    def __init__(self, uuid=None, apply_=None):
        if uuid:
            try:
                self.load()
                if self.uuid != uuid:
                    raise
            except:
                raise ValueError("UUID not found: %s - %s (on disk)" % (
                    uuid,
                    self.uuid,
                ))
        else:
            self.apply = apply_
            self.uuid = uuid4().hex
            self.details = ''
            self.indeterminate = False
            self.pid = None
            self.progress = 0
            self.step = 1
            self.finished = False
            self.error = False
            self.reboot = False
        self._pkgname = ''
        self._baseprogress = 0

    @classmethod
    def is_running(cls):
        if not os.path.exists(cls.DUMPFILE):
            return False

        with LockFile(cls.DUMPFILE) as lock:
            with open(cls.DUMPFILE, 'rb') as f:
                data = json.loads(f.read())

        pid = int(data.get('pid'))
        try:
            os.kill(pid, 0)
        except:
            return False
        else:
            return data['uuid']

    def get_handler(self, index, pkg, pkgList):
        self.step = 1
        self._pkgname = '%s-%s' % (
            pkg.Name(),
            pkg.Version(),
        )
        self.details = '%s %s' % (
            _('Downloading'),
            self._pkgname,
        )
        stepprogress = int((1.0 / float(len(pkgList))) * 100)
        self._baseprogress = index * stepprogress
        self.progress = (index - 1) * stepprogress
        self.dump()
        return self.get_file_handler

    def get_file_handler(
        self, method, filename, size=None, progress=None, download_rate=None
    ):
        filename = filename.rsplit('/', 1)[-1]
        if progress is not None:
            self.progress = (progress * self._baseprogress) / 100
            if self.progress == 0:
                self.progress = 1
            self.details = '%s<br />%s(%d%%)%s' % (
                filename,
                '%s ' % humanize_size(size)
                if size else '',
                progress,
                '  %s/s' % humanize_size(download_rate)
                if download_rate else '',
            )
        self.dump()

    def install_handler(self, index, name, packages):
        if self.apply:
            self.step = 2
        else:
            self.step = 1
        self.indeterminate = False
        total = len(packages)
        self.progress = int((float(index) / float(total)) * 100.0)
        self.details = '%s %s (%d/%d)' % (
            _('Installing'),
            name,
            index,
            total,
        )
        self.dump()

    def dump(self):
        with LockFile(self.DUMPFILE) as lock:
            with open(self.DUMPFILE, 'w') as f:
                data = {
                    'apply': self.apply,
                    'error': self.error,
                    'finished': self.finished,
                    'indeterminate': self.indeterminate,
                    'pid': self.pid,
                    'percent': self.progress,
                    'step': self.step,
                    'uuid': self.uuid,
                    'reboot': self.reboot,
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
        self.apply = data.get('apply', '')
        self.details = data.get('details', '')
        self.error = data['error']
        self.finished = data['finished']
        self.indeterminate = data['indeterminate']
        self.progress = data['percent']
        self.pid = data['pid']
        self.step = data['step']
        self.uuid = data['uuid']
        self.reboot = data['reboot']
        return data

    def exit(self):
        if os.path.exists(self.DUMPFILE):
            os.unlink(self.DUMPFILE)


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


def run_updated(train, location, download=True, apply=False):
    # Why not use subprocess module?
    # Because for some reason it was leaving a zombie process behind
    # My guess is that its related to fork within a thread and fds
    readfd, writefd = os.pipe()
    updated_pid = os.fork()
    if updated_pid == 0:
        os.close(readfd)
        os.dup2(writefd, 1)
        os.close(writefd)
        for i in range(3, 1024):
            try:
                os.close(i)
            except OSError:
                pass
        os.execv(
            "/usr/local/www/freenasUI/tools/updated.py",
            [
                "/usr/local/www/freenasUI/tools/updated.py",
                '-t', train,
                '-c', location,
            ] + (['-d'] if download else []) + (['-a'] if apply else []),
        )
    else:
        os.close(writefd)
        pid, returncode = os.waitpid(updated_pid, 0)
        returncode >>= 8
        uuid = os.read(readfd, 1024)
        if uuid:
            uuid = uuid.strip('\n')
        return returncode, uuid


def manual_update(path):
    from freenasUI.middleware.notifier import notifier
    from freenasUI.middleware.exceptions import MiddlewareError

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
    except Exception as e:
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


def debug_generate():
    from freenasUI.common.locks import mntlock
    from freenasUI.middleware.notifier import notifier
    from freenasUI.network.models import GlobalConfiguration
    _n = notifier()
    gc = GlobalConfiguration.objects.all().order_by('-id')[0]
    mntpt, direc, dump = debug_get_settings()

    standby_debug = None
    if not _n.is_freenas() and _n.failover_licensed():
        try:
            s = _n.failover_rpc()
            standby_debug = s.debug()
        except:
            log.error('Failed to get debug from standby node', exc_info=True)

    with mntlock(mntpt=mntpt):

        debug_run(direc)

        if standby_debug:
            debug_file = '%s/debug.tar' % direc
            _n.sync_file_recv(s, standby_debug, '%s/standby.txz' % direc)
            # provide correct hostnames
            if _n.failover_node() == 'A':
                my_hostname = gc.gc_hostname
                remote_hostname = gc.gc_hostname_b
            else:
                my_hostname = gc.gc_hostname_b
                remote_hostname = gc.gc_hostname
            with tarfile.open(debug_file, 'w') as tar:
                tar.add('%s/standby.txz' % direc, '%s.txz' % remote_hostname)
                tar.add(dump, '%s.txz' % my_hostname)


def factory_restore(request):
    from freenasUI.account.models import bsdUsers
    from freenasUI.middleware.notifier import notifier
    request.session['allow_reboot'] = True
    notifier().config_restore()
    user = bsdUsers.objects.filter(bsdusr_uid=0)[0]
    backend = get_backends()[0]
    user.backend = "%s.%s" % (backend.__module__, backend.__class__.__name__)
    login(request, user)
