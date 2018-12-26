#!/usr/local/bin/python
#
# Copyright (c) 2010-2011 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

""" Helper for FreeNAS to execute command line tools

This helper class abstracts operating system operations like starting,
stopping, restarting services out from the normal Django stuff and makes
future extensions/changes to the command system easier.  When used as a
command line utility, this helper class can also be used to do these
actions.
"""

from decimal import Decimal
import ctypes
import glob
import libzfs
import logging
import os
import re
import shutil
import signal
import socket
import sqlite3
from subprocess import Popen, PIPE
import subprocess
import sys
import syslog
import tarfile
import tempfile
import time

WWW_PATH = "/usr/local/www"
FREENAS_PATH = os.path.join(WWW_PATH, "freenasUI")
NEED_UPDATE_SENTINEL = '/data/need-update'
GELI_KEYPATH = '/data/geli'
GELI_KEY_SLOT = 0
GELI_RECOVERY_SLOT = 1
GELI_REKEY_FAILED = '/tmp/.rekey_failed'
PWENC_BLOCK_SIZE = 32
PWENC_FILE_SECRET = '/data/pwenc_secret'
PWENC_PADDING = b'{'
PWENC_CHECK = 'Donuts!'

if WWW_PATH not in sys.path:
    sys.path.append(WWW_PATH)
if FREENAS_PATH not in sys.path:
    sys.path.append(FREENAS_PATH)

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

import django
from django.apps import apps

# Avoid calling setup again which may dead-lock
if not apps.app_configs:
    django.setup()

from django.utils.translation import ugettext as _

from freenasUI.common.acl import (ACL_FLAGS_OS_WINDOWS, ACL_WINDOWS_FILE,
                                  ACL_MAC_FILE)
from freenasUI.common.freenasacl import ACL
from freenasUI.common.pipesubr import SIG_SETMASK
from freenasUI.common.system import (
    FREENAS_DATABASE,
    exclude_path,
    get_mounted_filesystems,
    umount,
    get_sw_name,
)
from freenasUI.common.warden import (Warden, WardenJail,
                                     WARDEN_TYPE_PLUGINJAIL,
                                     WARDEN_STATUS_RUNNING)
from freenasUI.freeadmin.hook import HookMetaclass
from freenasUI.middleware import zfs
from freenasUI.middleware.client import client
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.multipath import Multipath
import sysctl

RE_DSKNAME = re.compile(r'^([a-z]+)([0-9]+)$')
log = logging.getLogger('middleware.notifier')


class notifier(metaclass=HookMetaclass):

    from grp import getgrnam as ___getgrnam
    IDENTIFIER = 'notifier'

    def is_freenas(self):
        return True

    def _system(self, command):
        log.debug("Executing: %s", command)
        # TODO: python's signal class should be taught about sigprocmask(2)
        # This is hacky hack to work around this issue.
        libc = ctypes.cdll.LoadLibrary("libc.so.7")
        omask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        mask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        pmask = ctypes.pointer(mask)
        pomask = ctypes.pointer(omask)
        libc.sigprocmask(SIG_SETMASK, pmask, pomask)
        try:
            p = Popen(
                "(" + command + ") 2>&1",
                stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True, close_fds=True, encoding='utf8')
            syslog.openlog(self.IDENTIFIER, facility=syslog.LOG_DAEMON)
            for line in p.stdout:
                syslog.syslog(syslog.LOG_NOTICE, line)
            syslog.closelog()
            p.wait()
            ret = p.returncode
        finally:
            libc.sigprocmask(SIG_SETMASK, pomask, None)
        log.debug("Executed: %s -> %s", command, ret)
        return ret

    def _system_nolog(self, command):
        log.debug("Executing: %s", command)
        # TODO: python's signal class should be taught about sigprocmask(2)
        # This is hacky hack to work around this issue.
        libc = ctypes.cdll.LoadLibrary("libc.so.7")
        omask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        mask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        pmask = ctypes.pointer(mask)
        pomask = ctypes.pointer(omask)
        libc.sigprocmask(SIG_SETMASK, pmask, pomask)
        try:
            p = Popen(
                "(" + command + ") >/dev/null 2>&1",
                stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True, close_fds=True)
            p.communicate()
            retval = p.returncode
        finally:
            libc.sigprocmask(SIG_SETMASK, pomask, None)
        log.debug("Executed: %s; returned %d", command, retval)
        return retval

    def _pipeopen(self, command, logger=log):
        if logger:
            logger.debug("Popen()ing: %s", command)
        return Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True, close_fds=True, encoding='utf8')

    def _pipeerr(self, command, good_status=0):
        proc = self._pipeopen(command)
        err = proc.communicate()[1]
        if proc.returncode != good_status:
            log.debug("%s -> %s (%s)", command, proc.returncode, err)
            return err
        log.debug("%s -> %s", command, proc.returncode)
        return None

    def start(self, what, timeout=None, onetime=False, wait=None, sync=None):
        kwargs = {}
        if timeout:
            kwargs['timeout'] = timeout
        with client as c:
            return c.call(
                'service.start',
                what,
                {'onetime': onetime, 'wait': wait, 'sync': sync},
                **kwargs
            )

    def started(self, what, timeout=None):
        kwargs = {}
        if timeout:
            kwargs['timeout'] = timeout
        with client as c:
            return c.call('service.started', what, **kwargs)

    def stop(self, what, timeout=None, onetime=False, wait=None, sync=None):
        kwargs = {}
        if timeout:
            kwargs['timeout'] = timeout
        with client as c:
            return c.call(
                'service.stop',
                what,
                {'onetime': onetime, 'wait': wait, 'sync': sync},
                **kwargs,
            )

    def restart(self, what, timeout=None, onetime=False, wait=None, sync=None):
        kwargs = {}
        if timeout:
            kwargs['timeout'] = timeout
        with client as c:
            return c.call(
                'service.restart',
                what,
                {'onetime': onetime, 'wait': wait, 'sync': sync},
                **kwargs,
            )

    def reload(self, what, timeout=None, onetime=False, wait=None, sync=None):
        kwargs = {}
        if timeout:
            kwargs['timeout'] = timeout
        with client as c:
            return c.call(
                'service.reload',
                what,
                {'onetime': onetime, 'wait': wait, 'sync': sync},
                **kwargs,
            )

    def clear_activedirectory_config(self):
        with client as c:
            return c.call('service._clear_activedirectory_config')

    """
    The following plugins methods violate the service layer
    and are staying here now for compatibility.
    """
    def _start_plugins(self, jail=None, plugin=None):
        if jail and plugin:
            self._system("/usr/sbin/service ix-plugins forcestart %s:%s" % (jail, plugin))
        else:
            self._system("/usr/sbin/service ix-plugins forcestart")

    def _stop_plugins(self, jail=None, plugin=None):
        if jail and plugin:
            self._system("/usr/sbin/service ix-plugins forcestop %s:%s" % (jail, plugin))
        else:
            self._system("/usr/sbin/service ix-plugins forcestop")

    def _restart_plugins(self, jail=None, plugin=None):
        self._stop_plugins(jail=jail, plugin=plugin)
        self._start_plugins(jail=jail, plugin=plugin)

    def _started_plugins(self, jail=None, plugin=None):
        res = False
        if jail and plugin:
            if self._system("/usr/sbin/service ix-plugins status %s:%s" % (jail, plugin)) == 0:
                res = True
        else:
            if self._system("/usr/sbin/service ix-plugins status") == 0:
                res = True
        return res

    def pluginjail_running(self, pjail=None):
        running = False

        try:
            wlist = Warden().cached_list()
            for wj in wlist:
                wj = WardenJail(**wj)
                if pjail and wj.host == pjail:
                    if (
                        wj.type == WARDEN_TYPE_PLUGINJAIL and
                        wj.status == WARDEN_STATUS_RUNNING
                    ):
                        running = True
                        break

                elif (
                    not pjail and wj.type == WARDEN_TYPE_PLUGINJAIL and
                    wj.status == WARDEN_STATUS_RUNNING
                ):
                    running = True
                    break
        except Exception:
            pass

        return running

    def _open_db(self):
        """Open and return a cursor object for database access."""
        try:
            from freenasUI.settings import DATABASES
            dbname = DATABASES['default']['NAME']
        except Exception:
            dbname = '/data/freenas-v1.db'

        conn = sqlite3.connect(dbname)
        c = conn.cursor()
        return c, conn

    def geli_recoverykey_add(self, volume, passphrase=None):
        from freenasUI.middleware.util import download_job
        reckey = tempfile.NamedTemporaryFile(dir='/tmp/', delete=False)
        download_job(reckey.name, 'recovery.key', 'pool.recoverykey_add', volume.id, {})
        return reckey.name

    def geli_delkey(self, volume, slot=GELI_RECOVERY_SLOT, force=True):
        try:
            with client as c:
                c.call('pool.recoverykey_rm', volume.id)
        except Exception as e:
            raise MiddlewareError(f'Failed to remove recovery key: {str(e)}')

    def geli_is_decrypted(self, dev):
        doc = self._geom_confxml()
        geom = doc.xpath("//class[name = 'ELI']/geom[name = '%s.eli']" % (
            dev,
        ))
        if geom:
            return True
        return False

    def geli_detach(self, dev):
        """
        Detach geli provider

        Throws MiddlewareError if the detach failed
        """
        if os.path.exists("/dev/%s.eli" % dev):
            command = "geli detach %s" % dev
            err = self._pipeerr(command)
            if err or os.path.exists("/dev/%s.eli" % dev):
                raise MiddlewareError("Failed to geli detach %s: %s" % (dev, err))
        else:
            log.debug("%s already detached", dev)

    def geli_get_all_providers(self):
        """
        Get all unused geli providers

        It might be an entire disk or a partition of type freebsd-zfs
        """
        providers = []
        doc = self._geom_confxml()
        disks = self.get_disks()
        for disk in disks:
            parts = [node.text
                     for node in doc.xpath("//class[name = 'PART']/geom[name = '%s']"
                                           "/provider/config[type = 'freebsd-zfs']"
                                           "/../name" % disk)]
            if not parts:
                parts = [disk]
            for part in parts:
                proc = self._pipeopen("geli dump %s" % part)
                if proc.wait() == 0:
                    gptid = doc.xpath("//class[name = 'LABEL']/geom[name = '%s']"
                                      "/provider/name" % part)
                    if gptid:
                        providers.append((gptid[0].text, part))
                    else:
                        providers.append((part, part))
        return providers

    def zfs_offline_disk(self, volume, label):
        try:
            with client as c:
                c.call('pool.offline', volume.id, {'label': label})
        except Exception as e:
            raise MiddlewareError(f'Disk offline failed: {str(e)}')

    def zfs_online_disk(self, volume, label):
        try:
            with client as c:
                c.call('pool.online', volume.id, {'label': label})
        except Exception as e:
            raise MiddlewareError(f'Disk online failed: {str(e)}')

    def zfs_detach_disk(self, volume, label):
        from freenasUI.storage.models import Volume

        if isinstance(volume, str):
            volume = Volume.objects.get(vol_name=volume)

        try:
            with client as c:
                c.call('pool.detach', volume.id, {'label': label})
        except Exception as e:
            raise MiddlewareError(f'Failed to detach disk: {str(e)}')

    def zfs_remove_disk(self, volume, label):
        """
        Remove a disk from zpool
        Cache disks, inactive hot-spares (and log devices in zfs 28) can be removed
        """

        try:
            with client as c:
                c.call('pool.remove', volume.id, {'label': label})
        except Exception as e:
            raise MiddlewareError(f'Disk could not be removed: {str(e)}')

    def groupmap_list(self):
        command = "/usr/local/bin/net groupmap list"
        groupmap = []

        proc = self._pipeopen(command)
        out = proc.communicate()
        if proc.returncode != 0:
            return None

        out = out[0]
        lines = out.splitlines()
        for line in lines:
            m = re.match('^(?P<ntgroup>.+) \((?P<SID>S-[0-9\-]+)\) -> (?P<unixgroup>.+)$', line)
            if m:
                groupmap.append(m.groupdict())

        return groupmap

    def groupmap_add(self, unixgroup, ntgroup, type='local'):
        command = "/usr/local/bin/net groupmap add type=%s unixgroup='%s' ntgroup='%s'"

        ret = False
        proc = self._pipeopen(command % (
            type,
            unixgroup,
            ntgroup,
        ))
        proc.communicate()
        if proc.returncode == 0:
            ret = True

        return ret

    def groupmap_delete(self, ntgroup=None, sid=None):
        command = "/usr/local/bin/net groupmap delete "

        ret = False
        if not ntgroup and not sid:
            return ret

        if ntgroup:
            command = "%s ntgroup='%s'" % (command, ntgroup)
        elif sid:
            command = "%s sid='%s'" % (command, sid)

        proc = self._pipeopen(command)
        proc.communicate()
        if proc.returncode == 0:
            ret = True

        return ret

    def path_to_smb_share(self, path):
        from freenasUI.sharing.models import CIFS_Share

        try:
            share = CIFS_Share.objects.get(cifs_path=path)
        except Exception:
            share = None

        return share

    def owner_to_SID(self, owner):
        if not owner:
            return None

        proc = self._pipeopen("/usr/local/bin/wbinfo -n '%s'" % owner)

        info, err = proc.communicate()
        if proc.returncode != 0:
            log.debug("owner_to_SID: error %s", err)
            return None

        try:
            SID = info.split(' ')[0].strip()
        except Exception:
            SID = None

        log.debug("owner_to_SID: %s -> %s", owner, SID)
        return SID

    def group_to_SID(self, group):
        if not group:
            return None

        proc = self._pipeopen("/usr/local/bin/wbinfo -n '%s'" % group)

        info, err = proc.communicate()
        if proc.returncode != 0:
            log.debug("group_to_SID: error %s", err)
            return None

        try:
            SID = info.split(' ')[0].strip()
        except Exception:
            SID = None

        log.debug("group_to_SID: %s -> %s", group, SID)
        return SID

    def sharesec_add(self, share, owner, group):
        if not share:
            return False

        log.debug("sharesec_add: adding '%s:%s' ACL on %s", owner, group, share)

        add_args = ""
        sharesec = "/usr/local/bin/sharesec"

        owner_SID = self.owner_to_SID(owner)
        group_SID = self.group_to_SID(group)

        if owner and owner_SID:
            add_args += ",%s:ALLOWED/0/FULL" % owner_SID
        if group and group_SID:
            add_args += ",%s:ALLOWED/0/FULL" % group_SID
        add_args = add_args.lstrip(',')

        ret = True
        if add_args:
            add_cmd = "%s %s -a '%s'" % (sharesec, share, add_args)
            try:
                self._pipeopen(add_cmd).communicate()
            except Exception:
                log.debug("sharesec_add: %s failed", add_cmd)
                ret = False

        return ret

    def sharesec_delete(self, share):
        if not share:
            return False

        log.debug("sharesec_delete: deleting ACL on %s", share)

        sharesec = "/usr/local/bin/sharesec"
        delete_cmd = "%s %s -D" % (sharesec, share)

        ret = True
        try:
            self._pipeopen(delete_cmd).communicate()
        except Exception:
            log.debug("sharesec_delete: %s failed", delete_cmd)
            ret = False

        return ret

    def sharesec_reset(self, share, owner=None, group=None):
        if not share:
            return False

        log.debug("sharesec_reset: resetting %s to '%s:%s'", share, owner, group)

        self.sharesec_delete(share)
        return self.sharesec_add(share, owner, group)

    def winacl_reset(self, path, owner=None, group=None, exclude=None, recursive=True):
        if exclude is None:
            exclude = []

        if isinstance(owner, bytes):
            owner = owner.decode('utf-8')

        if isinstance(group, bytes):
            group = group.decode('utf-8')

        if isinstance(path, bytes):
            path = path.decode('utf-8')

        aclfile = os.path.join(path, ACL_WINDOWS_FILE)
        winexists = (ACL.get_acl_ostype(path) == ACL_FLAGS_OS_WINDOWS)
        if not winexists:
            open(aclfile, 'a').close()

        share = self.path_to_smb_share(path)
        self.sharesec_reset(share, owner, group)

        winacl = "/usr/local/bin/winacl"
        args = "-a reset"
        if owner is not None:
            args = "%s -O '%s'" % (args, owner)
        if group is not None:
            args = "%s -G '%s'" % (args, group)
        apply_paths = exclude_path(path, exclude)
        apply_paths = [(y, f' {"-r " if recursive else ""}') for y in apply_paths]
        if len(apply_paths) > 1:
            apply_paths.insert(0, (path, ''))
        for apath, flags in apply_paths:
            fargs = args + "%s -p '%s'" % (flags, apath)
            cmd = "%s %s" % (winacl, fargs)
            log.debug("winacl_reset: cmd = %s", cmd)
            self._system(cmd)

    def mp_change_permission(self, path='/mnt', user=None, group=None,
                             mode=None, recursive=False, acl='unix',
                             exclude=None):

        if exclude is None:
            exclude = []

        if isinstance(group, bytes):
            group = group.decode('utf-8')

        if isinstance(user, bytes):
            user = user.decode('utf-8')

        if isinstance(mode, bytes):
            mode = mode.decode('utf-8')

        if isinstance(path, bytes):
            path = path.decode('utf-8')

        winacl = os.path.join(path, ACL_WINDOWS_FILE)
        macacl = os.path.join(path, ACL_MAC_FILE)
        winexists = (ACL.get_acl_ostype(path) == ACL_FLAGS_OS_WINDOWS)
        with libzfs.ZFS() as zfs:
            zfs_dataset_name = zfs.get_dataset_by_path(path).name

        if acl == 'windows':
            if not winexists:
                open(winacl, 'a').close()
                winexists = True
            if os.path.isfile(macacl):
                os.unlink(macacl)
        elif acl == 'mac':
            if winexists:
                os.unlink(winacl)
            if not os.path.isfile(macacl):
                open(macacl, 'a').close()
        elif acl == 'unix':
            if winexists:
                os.unlink(winacl)
                winexists = False
            if os.path.isfile(macacl):
                os.unlink(macacl)

        if winexists:
            self.zfs_set_option(zfs_dataset_name, "aclmode", "restricted", recursive)
            script = "/usr/local/bin/winacl"
            args = ''
            if user is not None:
                args += " -O '%s'" % user
            if group is not None:
                args += " -G '%s'" % group
            args += " -a reset "
            if recursive:
                apply_paths = exclude_path(path, exclude)
                apply_paths = [(y, ' -r ') for y in apply_paths]
                if len(apply_paths) > 1:
                    apply_paths.insert(0, (path, ''))
            else:
                apply_paths = [(path, '')]
            for apath, flags in apply_paths:
                fargs = args + "%s -p '%s'" % (flags, apath)
                cmd = "%s %s" % (script, fargs)
                log.debug("XXX: CMD = %s", cmd)
                self._system(cmd)

        else:
            self.zfs_set_option(zfs_dataset_name, "aclmode", "passthrough", recursive)
            if recursive:
                apply_paths = exclude_path(path, exclude)
                apply_paths = [(y, '-R') for y in apply_paths]
                if len(apply_paths) > 1:
                    apply_paths.insert(0, (path, ''))
            else:
                apply_paths = [(path, '')]
            for apath, flags in apply_paths:
                if user is not None and group is not None:
                    self._system("/usr/sbin/chown %s '%s':'%s' '%s'" % (flags, user, group, apath))
                elif user is not None:
                    self._system("/usr/sbin/chown %s '%s' '%s'" % (flags, user, apath))
                elif group is not None:
                    self._system("/usr/sbin/chown %s :'%s' '%s'" % (flags, group, apath))
                if mode is not None:
                    self._system("/bin/chmod %s %s '%s'" % (flags, mode, apath))

        share = self.path_to_smb_share(path)
        if share:
            self.sharesec_reset(share, user, group)

    def change_upload_location(self, path):
        vardir = "/var/tmp/firmware"

        self._system("/bin/rm -rf %s" % vardir)
        self._system("/bin/mkdir -p %s/.freenas" % path)
        self._system("/usr/sbin/chown www:www %s/.freenas" % path)
        self._system("/bin/chmod 755 %s/.freenas" % path)
        self._system("/bin/ln -s %s/.freenas %s" % (path, vardir))

    def create_upload_location(self):
        """
        Create a temporary location for manual update
        over a memory device (mdconfig) using UFS

        Raises:
            MiddlewareError
        """

        sw_name = get_sw_name()
        label = "%smdu" % (sw_name, )
        doc = self._geom_confxml()

        pref = doc.xpath(
            "//class[name = 'LABEL']/geom/"
            "provider[name = 'label/%s']/../consumer/provider/@ref" % (label, )
        )
        if not pref:
            proc = self._pipeopen("/sbin/mdconfig -a -t swap -s 2800m")
            mddev, err = proc.communicate()
            if proc.returncode != 0:
                raise MiddlewareError("Could not create memory device: %s" % err)

            self._system("/sbin/glabel create %s %s" % (label, mddev))

            proc = self._pipeopen("newfs /dev/label/%s" % (label, ))
            err = proc.communicate()[1]
            if proc.returncode != 0:
                raise MiddlewareError("Could not create temporary filesystem: %s" % err)

            self._system("/bin/rm -rf /var/tmp/firmware")
            self._system("/bin/mkdir -p /var/tmp/firmware")
            proc = self._pipeopen("mount /dev/label/%s /var/tmp/firmware" % (label, ))
            err = proc.communicate()[1]
            if proc.returncode != 0:
                raise MiddlewareError("Could not mount temporary filesystem: %s" % err)

        self._system("/usr/sbin/chown www:www /var/tmp/firmware")
        self._system("/bin/chmod 755 /var/tmp/firmware")

    def destroy_upload_location(self):
        """
        Destroy a temporary location for manual update
        over a memory device (mdconfig) using UFS

        Raises:
            MiddlewareError

        Returns:
            bool
        """

        sw_name = get_sw_name()
        label = "%smdu" % (sw_name, )
        doc = self._geom_confxml()

        pref = doc.xpath(
            "//class[name = 'LABEL']/geom/"
            "provider[name = 'label/%s']/../consumer/provider/@ref" % (label, )
        )
        if not pref:
            return False
        prov = doc.xpath("//class[name = 'MD']//provider[@id = '%s']/name" % pref[0])
        if not prov:
            return False

        mddev = prov[0].text

        self._system("umount /dev/label/%s" % (label, ))
        proc = self._pipeopen("mdconfig -d -u %s" % (mddev, ))
        err = proc.communicate()[1]
        if proc.returncode != 0:
            raise MiddlewareError("Could not destroy memory device: %s" % err)

        return True

    def get_update_location(self):
        with client as c:
            syspath = c.call('systemdataset.config')['path']
        if syspath:
            return '%s/update' % syspath
        return '/var/tmp/update'

    def validate_update(self, path):

        os.chdir(os.path.dirname(path))

        # XXX: ugly
        self._system("rm -rf */")

        percent = 0
        with open('/tmp/.extract_progress', 'w') as fp:
            fp.write("2|%d\n" % percent)
            fp.flush()
            with open('/tmp/.upgrade_extract', 'w') as f:
                size = os.stat(path).st_size
                proc = subprocess.Popen([
                    "/usr/bin/tar",
                    "-xSJpf",  # -S for sparse
                    path,
                ], stderr=f, encoding='utf8')
                RE_TAR = re.compile(r"^In: (\d+)", re.M | re.S)
                while True:
                    if proc.poll() is not None:
                        break
                    try:
                        os.kill(proc.pid, signal.SIGINFO)
                    except Exception:
                        break
                    time.sleep(1)
                    # TODO: We don't need to read the whole file
                    with open('/tmp/.upgrade_extract', 'r') as f2:
                        line = f2.read()
                    reg = RE_TAR.findall(line)
                    if reg:
                        current = Decimal(reg[-1])
                        percent = int((current / size) * 100)
                        fp.write("2|%d\n" % percent)
                        fp.flush()
            err = proc.communicate()[1]
            if proc.returncode != 0:
                os.chdir('/')
                raise MiddlewareError(
                    'The firmware image is invalid, make sure to use .txz file: %s' % err
                )
            fp.write("3|\n")
            fp.flush()
        os.unlink('/tmp/.extract_progress')
        os.chdir('/')
        return True

    def apply_update(self, path):
        from freenasUI.system.views import INSTALLFILE
        import freenasOS.Configuration as Configuration
        dirpath = os.path.dirname(path)
        try:
            os.chmod(dirpath, 0o755)
        except OSError as e:
            raise MiddlewareError("Unable to set permissions on update cache directory %s: %s" % (dirpath, str(e)))
        open(INSTALLFILE, 'w').close()
        try:
            subprocess.check_output(
                '/usr/local/bin/manifest_util sequence 2> /dev/null > {}/SEQUENCE'.format(dirpath),
                shell=True,
            )
            conf = Configuration.Configuration()
            with open('{}/SERVER'.format(dirpath), 'w') as f:
                f.write('%s' % conf.UpdateServerName())
            subprocess.check_output(
                [
                    '/usr/local/bin/freenas-update',
                    '-C', dirpath,
                    'update',
                ],
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as cpe:
            raise MiddlewareError('Failed to apply update %s: %s' % (str(cpe), cpe.output))
        finally:
            os.chdir('/')
            try:
                os.unlink(path)
            except OSError:
                pass
            try:
                os.unlink(INSTALLFILE)
            except OSError:
                pass
        open(NEED_UPDATE_SENTINEL, 'w').close()

    def umount_filesystems_within(self, path):
        """
        Try to umount filesystems within a certain path

        Raises:
            MiddlewareError - Could not umount
        """
        for mounted in get_mounted_filesystems():
            if mounted['fs_file'].startswith(path):
                if not umount(mounted['fs_file']):
                    raise MiddlewareError('Unable to umount %s' % (
                        mounted['fs_file'],
                    ))

    def contains_jail_root(self, path):
        try:
            rpath = os.path.realpath(path)
        except Exception as e:
            log.debug("realpath %s: %s", path, e)
            return False

        rpath = os.path.normpath(rpath)

        try:
            os.stat(rpath)
        except Exception as e:
            log.debug("stat %s: %s", rpath, e)
            return False

        (c, conn) = self._open_db()
        try:
            c.execute("SELECT jc_path FROM jails_jailsconfiguration LIMIT 1")
            row = c.fetchone()
        finally:
            conn.close()
        if not row:
            log.debug("contains_jail_root: jails not configured")
            return False

        try:
            jail_root = os.path.realpath(row[0])
        except Exception as e:
            log.debug("realpath %s: %s", jail_root, e)
            return False

        jail_root = os.path.normpath(jail_root)

        try:
            os.stat(jail_root)
        except Exception as e:
            log.debug("stat %s: %s", jail_root, e)
            return False

        if jail_root.startswith(rpath):
            return True

        return False

    def delete_plugins(self, force=False):
        from freenasUI.plugins.models import Plugins
        for p in Plugins.objects.all():
            p.delete(force=force)

    def get_volume_status(self, name):
        status = 'UNKNOWN'
        p1 = self._pipeopen('zpool list -H -o health %s' % str(name), logger=None)
        if p1.wait() == 0:
            status = p1.communicate()[0].strip('\n')
        if status == 'ONLINE':
            status = 'HEALTHY'
        return status

    def get_disks(self, unused=False):
        """
        Grab usable disks and pertinent info about them
        This accounts for:
            - all the disks the OS found
                (except the ones that are providers for multipath)
            - multipath geoms providers

        Arguments:
            unused(bool) - return only disks unused by volume or extent disk

        Returns:
            Dict of disks
        """
        disksd = {}

        disks = self.__get_disks()

        """
        Replace devnames by its multipath equivalent
        """
        for mp in self.multipath_all():
            for dev in mp.devices:
                if dev in disks:
                    disks.remove(dev)
            disks.append(mp.devname)

        for disk in disks:
            info = self._pipeopen('/usr/sbin/diskinfo %s' % disk).communicate()[0].split('\t')
            if len(info) > 3:
                disksd.update({
                    disk: {
                        'devname': info[0],
                        'capacity': info[2],
                    },
                })

        for mp in self.multipath_all():
            for consumer in mp.consumers:
                if consumer.lunid and mp.devname in disksd:
                    disksd[mp.devname]['ident'] = consumer.lunid
                    break

        if unused:
            """
            Remove disks that are in use by volumes or disk extent
            """
            from freenasUI.storage.models import Volume
            from freenasUI.services.models import iSCSITargetExtent

            for v in Volume.objects.all():
                for d in v.get_disks():
                    if d in disksd:
                        del disksd[d]

            for e in iSCSITargetExtent.objects.filter(iscsi_target_extent_type='Disk'):
                d = e.get_device()[5:]
                if d in disksd:
                    del disksd[d]

        return disksd

    def get_partitions(self, try_disks=True):
        disks = list(self.get_disks().keys())
        partitions = {}
        for disk in disks:

            listing = glob.glob('/dev/%s[a-fps]*' % disk)
            if try_disks is True and len(listing) == 0:
                listing = [disk]
            for part in list(listing):
                toremove = len([i for i in listing if i.startswith(part) and i != part]) > 0
                if toremove:
                    listing.remove(part)

            for part in listing:
                p1 = Popen(["/usr/sbin/diskinfo", part], stdin=PIPE, stdout=PIPE, encoding='utf8')
                info = p1.communicate()[0].split('\t')
                partitions.update({
                    part: {
                        'devname': info[0].replace("/dev/", ""),
                        'capacity': info[2]
                    },
                })
        return partitions

    def precheck_partition(self, dev, fstype):

        if fstype == 'UFS':
            p1 = self._pipeopen("/sbin/fsck_ufs -p %s" % dev)
            p1.communicate()
            if p1.returncode == 0:
                return True
        elif fstype == 'NTFS':
            return True
        elif fstype == 'MSDOSFS':
            p1 = self._pipeopen("/sbin/fsck_msdosfs -p %s" % dev)
            p1.communicate()
            if p1.returncode == 0:
                return True
        elif fstype == 'EXT2FS':
            p1 = self._pipeopen("/sbin/fsck_ext2fs -p %s" % dev)
            p1.communicate()
            if p1.returncode == 0:
                return True

        return False

    def label_disk(self, label, dev, fstype=None):
        """
        Label the disk being manually imported
        Currently UFS, NTFS, MSDOSFS and EXT2FS are supported
        """

        if fstype == 'UFS':
            p1 = Popen(["/sbin/tunefs", "-L", label, dev], stdin=PIPE, stdout=PIPE)
        elif fstype == 'NTFS':
            p1 = Popen(["/usr/local/sbin/ntfslabel", dev, label], stdin=PIPE, stdout=PIPE)
        elif fstype == 'MSDOSFS':
            p1 = Popen(["/usr/local/bin/mlabel", "-i", dev, "::%s" % label], stdin=PIPE, stdout=PIPE)
        elif fstype == 'EXT2FS':
            p1 = Popen(["/usr/local/sbin/tune2fs", "-L", label, dev], stdin=PIPE, stdout=PIPE)
        elif fstype is None:
            p1 = Popen(["/sbin/geom", "label", "label", label, dev], stdin=PIPE, stdout=PIPE)
        else:
            return False, 'Unknown fstype %r' % fstype
        err = p1.communicate()[1]
        if p1.returncode == 0:
            return True, ''
        return False, err

    def zfs_import(self, name, id=None, first_time=True):
        if id is not None:
            imp = self._pipeopen('zpool import -f -R /mnt %s' % id)
        else:
            imp = self._pipeopen('zpool import -f -R /mnt %s' % name)
        stdout, stderr = imp.communicate()

        # zpool import may fail due to readonly mountpoint but pool
        # will be imported so we make sure of that using libzfs.
        # See #24936
        imported = imp.returncode == 0
        if not imported:
            try:
                with libzfs.ZFS() as zfs:
                    imported = zfs.get(name) is not None
            except libzfs.ZFSException:
                pass

        if imported:
            # Remember the pool cache
            self._system("zpool set cachefile=/data/zfs/zpool.cache %s" % (name))
            if first_time:
                # Reset all mountpoints in the zpool
                self.zfs_inherit_option(name, 'mountpoint', True)
                # These should probably be options that are configurable from the GUI
                self._system("zfs set aclmode=passthrough '%s'" % name)
                self._system("zfs set aclinherit=passthrough '%s'" % name)
            return True
        else:
            log.error("Importing %s [%s] failed with: %s", name, id, stderr)
        return False

    def zfs_snapshot_list(self, path=None, sort=None, system=False):
        from freenasUI.storage.models import Volume
        fsinfo = dict()

        if sort is None:
            sort = ''
        else:
            sort = '-s %s' % sort

        if system is False:
            with client as c:
                basename = c.call('systemdataset.config')['basename']

        zfsproc = self._pipeopen("/sbin/zfs list -t volume -o name %s -H" % sort)
        zvols = set([y for y in zfsproc.communicate()[0].split('\n') if y != ''])
        volnames = set([o.vol_name for o in Volume.objects.all()])

        fieldsflag = '-o name,used,available,referenced,mountpoint,freenas:vmsynced'
        if path:
            zfsproc = self._pipeopen("/sbin/zfs list -p -r -t snapshot %s -H -S creation '%s'" % (fieldsflag, path))
        else:
            zfsproc = self._pipeopen("/sbin/zfs list -p -t snapshot -H -S creation %s" % (fieldsflag))
        lines = zfsproc.communicate()[0].split('\n')
        for line in lines:
            if line != '':
                _list = line.split('\t')
                snapname = _list[0]
                used = int(_list[1])
                refer = int(_list[3])
                vmsynced = _list[5]
                fs, name = snapname.split('@')

                if system is False and basename:
                    if fs == basename or fs.startswith(basename + '/'):
                        continue

                # Do not list snapshots from the root pool
                if fs.split('/')[0] not in volnames:
                    continue
                try:
                    snaplist = fsinfo[fs]
                    mostrecent = False
                except Exception:
                    snaplist = []
                    mostrecent = True

                snaplist.insert(0, zfs.Snapshot(
                    name=name,
                    filesystem=fs,
                    used=used,
                    refer=refer,
                    mostrecent=mostrecent,
                    parent_type='filesystem' if fs not in zvols else 'volume',
                    vmsynced=(vmsynced == 'Y')
                ))
                fsinfo[fs] = snaplist
        return fsinfo

    def zfs_clonesnap(self, snapshot, dataset):
        zfsproc = self._pipeopen("zfs clone '%s' '%s'" % (snapshot, dataset))
        retval = zfsproc.communicate()[1]
        return retval

    def config_restore(self):
        if os.path.exists("/data/freenas-v1.db.factory"):
            os.unlink("/data/freenas-v1.db.factory")
        save_path = os.getcwd()
        os.chdir(FREENAS_PATH)
        proc = self._pipeopen("/usr/local/sbin/migrate93 -f /data/freenas-v1.db.factory")
        error = proc.communicate()[1]
        if proc.returncode != 0:
            log.warn('Failed to create factory database: %s', error)
            raise MiddlewareError("Factory reset has failed, check /var/log/messages")
        proc = self._pipeopen("/usr/bin/env FREENAS_FACTORY=1 /usr/local/bin/python manage.py migrate --noinput --fake-initial")
        error = proc.communicate()[1]
        if proc.returncode != 0:
            log.warn('Failed to create factory database: %s', error)
            raise MiddlewareError("Factory reset has failed, check /var/log/messages")
        self._system("mv /data/freenas-v1.db.factory /data/freenas-v1.db")
        os.chdir(save_path)

    def config_upload(self, config_file_name):
        try:
            """
            First we try to open the file as a tar file.
            We expect the tar file to contain at least the freenas-v1.db.
            It can also contain the pwenc_secret file.
            If we cannot open it as a tar, we try to proceed as it was the
            raw database file.
            """
            try:
                with tarfile.open(config_file_name) as tar:
                    bundle = True
                    tmpdir = tempfile.mkdtemp(dir='/var/tmp/firmware')
                    tar.extractall(path=tmpdir)
                    config_file_name = os.path.join(tmpdir, 'freenas-v1.db')
            except tarfile.ReadError:
                bundle = False
            conn = sqlite3.connect(config_file_name)
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM south_migrationhistory WHERE app_name != 'freeadmin'")
                new_num = cur.fetchone()[0]
                cur.close()
            finally:
                conn.close()
            conn = sqlite3.connect(FREENAS_DATABASE)
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM south_migrationhistory WHERE app_name != 'freeadmin'")
                num = cur.fetchone()[0]
                cur.close()
            finally:
                conn.close()
                if new_num > num:
                    return False, _(
                        "Failed to upload config, version newer than the "
                        "current installed."
                    )
        except Exception:
            os.unlink(config_file_name)
            return False, _('The uploaded file is not valid.')

        shutil.move(config_file_name, '/data/uploaded.db')
        if bundle:
            secret = os.path.join(tmpdir, 'pwenc_secret')
            if os.path.exists(secret):
                shutil.move(secret, PWENC_FILE_SECRET)

        # Now we must run the migrate operation in the case the db is older
        open(NEED_UPDATE_SENTINEL, 'w+').close()

        return True, None

    def zfs_get_options(self, name=None, recursive=False, props=None, zfstype=None):
        noinherit_fields = ['quota', 'refquota', 'reservation', 'refreservation']

        if props is None:
            props = 'all'
        else:
            props = ','.join(props)

        if zfstype is None:
            zfstype = 'filesystem,volume'

        zfsproc = self._pipeopen("/sbin/zfs get %s -H -o name,property,value,source -t %s %s %s" % (
            '-r' if recursive else '',
            zfstype,
            props,
            "'%s'" % str(name) if name else '',
        ))
        zfs_output = zfsproc.communicate()[0]
        retval = {}
        for line in zfs_output.split('\n'):
            if not line:
                continue
            data = line.split('\t')
            if recursive:
                if data[0] not in retval:
                    dval = retval[data[0]] = {}
                else:
                    dval = retval[data[0]]
            else:
                dval = retval
            if (not data[1] in noinherit_fields) and (
                data[3] == 'default' or data[3].startswith('inherited')
            ):
                dval[data[1]] = (data[2], "inherit (%s)" % data[2], 'inherit')
            else:
                dval[data[1]] = (data[2], data[2], data[3])
        return retval

    def zfs_set_option(self, name, item, value, recursive=False):
        """
        Set a ZFS attribute using zfs set

        Returns:
            tuple(bool, str)
                bool -> Success?
                str -> Error message in case of error
        """
        name = str(name)
        item = str(item)

        if isinstance(value, bytes):
            value = value.decode('utf8')
        else:
            value = str(value)
        # Escape single quotes because of shell call
        value = value.replace("'", "'\"'\"'")
        if recursive:
            zfsproc = self._pipeopen("/sbin/zfs set -r '%s'='%s' '%s'" % (item, value, name))
        else:
            zfsproc = self._pipeopen("/sbin/zfs set '%s'='%s' '%s'" % (item, value, name))
        err = zfsproc.communicate()[1]
        if zfsproc.returncode == 0:
            return True, None
        return False, err

    def zfs_inherit_option(self, name, item, recursive=False):
        """
        Inherit a ZFS attribute using zfs inherit

        Returns:
            tuple(bool, str)
                bool -> Success?
                str -> Error message in case of error
        """
        name = str(name)
        item = str(item)
        if recursive:
            zfscmd = "zfs inherit -r %s '%s'" % (item, name)
        else:
            zfscmd = "zfs inherit %s '%s'" % (item, name)
        zfsproc = self._pipeopen(zfscmd)
        err = zfsproc.communicate()[1]
        if zfsproc.returncode == 0:
            return True, None
        return False, err

    def iface_media_status(self, name):

        statusmap = {
            'active': _('Active'),
            'BACKUP': _('Backup'),
            'INIT': _('Init'),
            'MASTER': _('Master'),
            'no carrier': _('No carrier'),
        }

        proc = self._pipeopen('/sbin/ifconfig %s' % name)
        data = proc.communicate()[0]

        if name.startswith('lagg'):
            proto = re.search(r'laggproto (\S+)', data)
            if not proto:
                return _('Unknown')
            proto = proto.group(1)
            ports = re.findall(r'laggport.+<(.*?)>', data, re.M | re.S)
            if proto == 'lacp':
                # Only if all ports are ACTIVE,COLLECTING,DISTRIBUTING
                # it is considered active

                portsok = len([y for y in ports if y == 'ACTIVE,COLLECTING,DISTRIBUTING'])
                if portsok == len(ports):
                    return _('Active')
                elif portsok > 0:
                    return _('Degraded')
                else:
                    return _('Down')

        if name.startswith('carp'):
            reg = re.search(r'carp: (\S+)', data)
        else:
            reg = re.search(r'status: (.+)$', data, re.MULTILINE)

        if proc.returncode != 0 or not reg:
            return _('Unknown')
        status = reg.group(1)

        return statusmap.get(status, status)

    def get_default_ipv4_interface(self):
        p1 = self._pipeopen("route -nv show default|grep 'interface:'|awk '{ print $2 }'")
        iface = p1.communicate()
        if p1.returncode != 0:
            iface = None
        try:
            iface = iface[0].strip()

        except Exception:
            pass

        return iface if iface else None

    def get_default_ipv6_interface(self):
        p1 = self._pipeopen("route -nv show -inet6 default|grep 'interface:'|awk '{ print $2 }'")
        iface = p1.communicate()
        if p1.returncode != 0:
            iface = None
        try:
            iface = iface[0].strip()

        except Exception:
            pass

        return iface if iface else None

    def get_default_interface(self, ip_protocol='ipv4'):
        iface = None

        if ip_protocol == 'ipv4':
            iface = self.get_default_ipv4_interface()
        elif ip_protocol == 'ipv6':
            iface = self.get_default_ipv6_interface()

        return iface

    def get_interface_info(self, iface):
        if not iface:
            return None

        iface_info = {'ether': None, 'ipv4': None, 'ipv6': None, 'status': None}
        p = self._pipeopen("ifconfig '%s'" % iface)
        out = p.communicate()
        if p.returncode != 0:
            return iface_info

        try:
            out = out[0].strip()
        except Exception:
            return iface_info

        m = re.search('ether (([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})', out, re.MULTILINE)
        if m is not None:
            iface_info['ether'] = m.group(1)

        lines = out.splitlines()
        for line in lines:
            line = line.lstrip().rstrip()
            m = re.search(
                'inet (([0-9]{1,3}\.){3}[0-9]{1,3})'
                ' +netmask (0x[0-9a-fA-F]{8})'
                '( +broadcast (([0-9]{1,3}\.){3}[0-9]{1,3}))?',
                line
            )

            if m is not None:
                if iface_info['ipv4'] is None:
                    iface_info['ipv4'] = []

                iface_info['ipv4'].append({
                    'inet': m.group(1),
                    'netmask': m.group(3),
                    'broadcast': m.group(4)
                })

            m = re.search('inet6 ([0-9a-fA-F:]+) +prefixlen ([0-9]+)', line)
            if m is not None:
                if iface_info['ipv6'] is None:
                    iface_info['ipv6'] = []

                iface_info['ipv6'].append({
                    'inet6': m.group(1),
                    'prefixlen': m.group(2)
                })

        m = re.search('status: (.+)$', out)
        if m is not None:
            iface_info['status'] = m.group(1)

        return iface_info

    def interface_is_ipv4(self, addr):
        res = False

        try:
            socket.inet_aton(addr)
            res = True

        except Exception:
            res = False

        return res

    def interface_is_ipv6(self, addr):
        res = False

        try:
            socket.inet_pton(socket.AF_INET6, addr)
            res = True

        except Exception:
            res = False

        return res

    def get_interface(self, addr):
        from freenasUI import choices

        if not addr:
            return None

        nic_choices = choices.NICChoices(exclude_configured=False)
        for nic in nic_choices:
            iface = str(nic[0])
            iinfo = self.get_interface_info(iface)
            if not iinfo:
                return None

            if self.interface_is_ipv4(addr):
                ipv4_info = iinfo['ipv4']
                if ipv4_info:
                    for i in ipv4_info:
                        if 'inet' not in i:
                            continue
                        ipv4_addr = i['inet']
                        if ipv4_addr == addr:
                            return nic[0]

            elif self.interface_is_ipv6(addr):
                ipv6_info = iinfo['ipv6']
                if ipv6_info:
                    for i in ipv6_info:
                        if 'inet6' not in i:
                            continue
                        ipv6_addr = i['inet6']
                        if ipv6_addr == addr:
                            return nic[0]

        return None

    def __init__(self):
        self.__confxml = None

    def __del__(self):
        self.__confxml = None

    def _geom_confxml(self):
        from lxml import etree
        if self.__confxml is None:
            self.__confxml = etree.fromstring(self.sysctl('kern.geom.confxml'))
        return self.__confxml

    def label_to_disk(self, name):
        """
        Given a label go through the geom tree to find out the disk name
        label = a geom label or a disk partition
        """
        doc = self._geom_confxml()

        # try to find the provider from GEOM_LABEL
        search = doc.xpath("//class[name = 'LABEL']//provider[name = '%s']/../consumer/provider/@ref" % name)
        if len(search) > 0:
            provider = search[0]
        else:
            # the label does not exist, try to find it in GEOM DEV
            search = doc.xpath("//class[name = 'DEV']/geom[name = '%s']//provider/@ref" % name)
            if len(search) > 0:
                provider = search[0]
            else:
                return None
        search = doc.xpath("//provider[@id = '%s']/../name" % provider)
        disk = search[0].text
        if search[0].getparent().getparent().xpath("./name")[0].text in ('ELI', ):
            return self.label_to_disk(disk.replace(".eli", ""))
        return disk

    def zpool_parse(self, name):
        doc = self._geom_confxml()
        p1 = self._pipeopen("zpool status %s" % name)
        res = p1.communicate()[0]
        parse = zfs.parse_status(name, doc, res)
        return parse

    def zpool_scrubbing(self):
        p1 = self._pipeopen("zpool status")
        res = p1.communicate()[0]
        r = re.compile(r'scan: (resilver|scrub) in progress')
        return r.search(res) is not None

    def multipath_all(self):
        """
        Get all available gmultipath instances

        Returns:
            A list of Multipath objects
        """
        doc = self._geom_confxml()
        return [
            Multipath(doc=doc, xmlnode=geom)
            for geom in doc.xpath("//class[name = 'MULTIPATH']/geom")
        ]

    def _find_root_devs(self):
        """Find the root device.

        Returns:
             The root device name in string format

        """

        try:
            zpool = self.zpool_parse('freenas-boot')
            return zpool.get_disks()
        except Exception:
            log.warn("Root device not found!")
            return []

    def __get_disks(self):
        """Return a list of available storage disks.

        The list excludes all devices that cannot be reserved for storage,
        e.g. the root device, CD drives, etc.

        Returns:
            A list of available devices (ada0, da0, etc), or an empty list if
            no devices could be divined from the system.
        """

        disks = self.sysctl('kern.disks').split()
        disks.reverse()

        blacklist_devs = self._find_root_devs()
        device_blacklist_re = re.compile('a?cd[0-9]+')

        return [x for x in disks if not device_blacklist_re.match(x) and x not in blacklist_devs]

    def sysctl(self, name):
        """
        Tiny wrapper for sysctl module for compatibility
        """
        sysc = sysctl.filter(str(name))
        if sysc:
            return sysc[0].value
        raise ValueError(name)

    def staticroute_delete(self, sr):
        """
        Delete a static route from the route table

        Raises:
            MiddlewareError in case the operation failed
        """
        import ipaddr
        netmask = ipaddr.IPNetwork(sr.sr_destination)
        masked = netmask.masked().compressed
        p1 = self._pipeopen("/sbin/route delete %s" % masked)
        if p1.wait() != 0:
            raise MiddlewareError("Failed to remove the route %s" % sr.sr_destination)

    def dataset_init_unix(self, dataset):
        """path = "/mnt/%s" % dataset"""
        pass

    def dataset_init_windows_meta_file(self, dataset):
        path = "/mnt/%s" % dataset
        with open("%s/.windows" % path, "w") as f:
            f.close()

    def dataset_init_windows(self, dataset):
        acl = [
            "owner@:rwxpDdaARWcCos:fd:allow",
            "group@:rwxpDdaARWcCos:fd:allow",
            "everyone@:rxaRc:fd:allow"
        ]

        self.dataset_init_windows_meta_file(dataset)

        path = "/mnt/%s" % dataset
        for ace in acl:
            self._pipeopen("/bin/setfacl -m '%s' '%s'" % (ace, path)).wait()

    def dataset_init_apple_meta_file(self, dataset):
        path = "/mnt/%s" % dataset
        with open("%s/.apple" % path, "w") as f:
            f.close()

    def dataset_init_apple(self, dataset):
        self.dataset_init_apple_meta_file(dataset)

    def get_dataset_share_type(self, dataset):
        share_type = "unix"

        path = "/mnt/%s" % dataset
        if os.path.exists("%s/.windows" % path):
            share_type = "windows"
        elif os.path.exists("%s/.apple" % path):
            share_type = "mac"

        return share_type

    def change_dataset_share_type(self, dataset, changeto):
        share_type = self.get_dataset_share_type(dataset)

        if changeto == "windows":
            self.dataset_init_windows_meta_file(dataset)
            self.zfs_set_option(dataset, "aclmode", "restricted")

        elif changeto == "mac":
            self.dataset_init_apple_meta_file(dataset)
            self.zfs_set_option(dataset, "aclmode", "passthrough")

        else:
            self.zfs_set_option(dataset, "aclmode", "passthrough")

        path = None
        if share_type == "mac" and changeto != "mac":
            path = "/mnt/%s/.apple" % dataset
        elif share_type == "windows" and changeto != "windows":
            path = "/mnt/%s/.windows" % dataset

        if path and os.path.exists(path):
            os.unlink(path)

    def rsync_command(self, obj_or_id):
        """
        Helper method used in ix-crontab to generate the rsync command
        avoiding code duplication.
        This should be removed once ix-crontab is rewritten in python.
        """
        from freenasUI.tasks.models import Rsync
        oid = int(obj_or_id)
        rsync = Rsync.objects.get(id=oid)
        return rsync.commandline()

    def zpool_status(self, pool_name):
        """
        Function to find out the status of the zpool
        It takes the name of the zpool (as a string) as the
        argument. It returns with a tuple of (state, status)
        """
        status = ''
        state = ''
        p1 = self._pipeopen("/sbin/zpool status -x %s" % pool_name, logger=None)
        zpool_result = p1.communicate()[0]
        if zpool_result.find("pool '%s' is healthy" % pool_name) != -1:
            state = 'HEALTHY'
        else:
            reg1 = re.search('^\s*state: (\w+)', zpool_result, re.M)
            if reg1:
                state = reg1.group(1)
            else:
                # The default case doesn't print out anything helpful,
                # but instead coredumps ;).
                state = 'UNKNOWN'
            reg1 = re.search(r'^\s*status: (.+)\n\s*action+:',
                             zpool_result, re.S | re.M)
            if reg1:
                msg = reg1.group(1)
                status = re.sub(r'\s+', ' ', msg)
            # Ignoring the action for now.
            # Deal with it when we can parse it, interpret it and
            # come up a gui link to carry out that specific repair.
            # action = ""
            # reg2 = re.search(r'^\s*action: ([^:]+)\n\s*\w+:',
            #                  zpool_result, re.S | re.M)
            # if reg2:
            #    msg = reg2.group(1)
            #    action = re.sub(r'\s+', ' ', msg)
        return (state, status)

    def pwenc_encrypt(self, text):
        if isinstance(text, bytes):
            text = text.decode('utf8')
        with client as c:
            return c.call('pwenc.encrypt', text)

    def pwenc_decrypt(self, encrypted=None):
        if not encrypted:
            return ""
        with client as c:
            return c.call('pwenc.decrypt', encrypted)

    def iscsi_connected_targets(self):
        '''
        Returns the list of connected iscsi targets
        '''
        from lxml import etree
        proc = self._pipeopen('ctladm islist -x')
        xml = proc.communicate()[0]
        connections = etree.fromstring(xml)
        connected_targets = []
        for connection in connections.xpath("//connection"):
            # Get full target name (Base name:target name) for each connection
            target = connection.xpath("./target")[0].text
            if target not in connected_targets:
                connected_targets.append(target)
        return connected_targets

    def iscsi_active_connections(self):
        from lxml import etree
        proc = self._pipeopen('ctladm islist -x')
        xml = proc.communicate()[0]
        xml = etree.fromstring(xml)
        connections = xml.xpath('//connection')
        return len(connections)

    def backup_db(self):
        from freenasUI.common.system import backup_database
        backup_database()

    def alua_enabled(self):
        if self.is_freenas() or not self.failover_licensed():
            return False
        from freenasUI.support.utils import fc_enabled
        if fc_enabled():
            return True
        from freenasUI.services.models import iSCSITargetGlobalConfiguration
        qs = iSCSITargetGlobalConfiguration.objects.all()
        if qs:
            return qs[0].iscsi_alua
        return False


def usage():
    usage_str = """usage: %s action command
    Action is one of:
        start: start a command
        stop: stop a command
        restart: restart a command
        reload: reload a command (try reload; if unsuccessful do restart)
        change: notify change for a command (try self.reload; if unsuccessful do start)""" \
        % (os.path.basename(sys.argv[0]), )
    sys.exit(usage_str)


# When running as standard-alone script
if __name__ == '__main__':
    if len(sys.argv) < 2:
        usage()
    else:
        n = notifier()
        f = getattr(n, sys.argv[1], None)
        if f is None:
            sys.stderr.write("Unknown action: %s\n" % sys.argv[1])
            usage()
        res = f(*sys.argv[2:])
        if res is not None:
            print(res)
