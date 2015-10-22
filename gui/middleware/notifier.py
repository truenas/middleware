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

from collections import defaultdict
import base64
from Crypto.Cipher import AES
import ctypes
import errno
import glob
import grp
import json
import logging
import os
import pwd
import re
import shutil
import signal
import socket
import sqlite3
import stat
from subprocess import Popen, PIPE
import subprocess
import sys
import tempfile
import threading
import time
import types

WWW_PATH = "/usr/local/www"
FREENAS_PATH = os.path.join(WWW_PATH, "freenasUI")
NEED_UPDATE_SENTINEL = '/data/need-update'
VERSION_FILE = '/etc/version'
GELI_KEYPATH = '/data/geli'
GELI_KEY_SLOT = 0
GELI_RECOVERY_SLOT = 1
SYSTEMPATH = '/var/db/system'
PWENC_BLOCK_SIZE = 32
PWENC_FILE_SECRET = '/data/pwenc_secret'
PWENC_PADDING = '{'
PWENC_CHECK = 'Donuts!'
BACKUP_SOCK = '/var/run/backupd.sock'

sys.path.append(WWW_PATH)
sys.path.append(FREENAS_PATH)

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

from django.db.models import Q

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from django.utils.translation import ugettext as _

RE_DSKNAME = re.compile(r'^([a-z]+)([0-9]+)$')
log = logging.getLogger('middleware.notifier')


class StartNotify(threading.Thread):

    def __init__(self, pidfile, verb, *args, **kwargs):
        self._pidfile = pidfile
        self._verb = verb
        super(StartNotify, self).__init__(*args, **kwargs)

    def run(self):
        """
        If we are using start or restart we expect that a .pid file will
        exists at the end of the process, so we wait for said pid file to
        be created and check if its contents are non-zero.
        Otherwise we will be stopping and expect the .pid to be deleted,
        so wait for it to be removed
        """
        if not self._pidfile:
            return None

        tries = 1
        while tries < 6:
            time.sleep(1)
            if self._verb in ('start', 'restart'):
                if os.path.exists(self._pidfile):
                    # The file might have been created but it may take a
                    # little bit for the daemon to write the PID
                    time.sleep(0.1)
                if (os.path.exists(self._pidfile)
                    and os.stat(self._pidfile).st_size > 0):
                    break
            elif self._verb == "stop" and not os.path.exists(self._pidfile):
                break
            tries += 1


class notifier:

    from os import system as __system
    from pwd import getpwnam as ___getpwnam
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
        libc.sigprocmask(signal.SIGQUIT, pmask, pomask)
        try:
            ret = self.__system("(" + command + ") 2>&1 | logger -p daemon.notice -t %s"
                                % (self.IDENTIFIER, ))
        finally:
            libc.sigprocmask(signal.SIGQUIT, pomask, None)
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
        libc.sigprocmask(signal.SIGQUIT, pmask, pomask)
        try:
            retval = self.__system("(" + command + ") >/dev/null 2>&1")
        finally:
            libc.sigprocmask(signal.SIGQUIT, pomask, None)
        retval >>= 8
        log.debug("Executed: %s; returned %d", command, retval)
        return retval

    def _pipeopen(self, command, logger=log):
        if logger:
            logger.debug("Popen()ing: %s", command)
        return Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True, close_fds=False)

    def _pipeerr(self, command, good_status=0):
        proc = self._pipeopen(command)
        err = proc.communicate()[1]
        if proc.returncode != good_status:
            log.debug("%s -> %s (%s)", command, proc.returncode, err)
            return err
        log.debug("%s -> %s", command, proc.returncode)
        return None

    def _do_nada(self):
        pass

    def _simplecmd(self, action, what):
        log.debug("Calling: %s(%s) ", action, what)
        f = getattr(self, '_' + action + '_' + what, None)
        if f is None:
            # Provide generic start/stop/restart verbs for rc.d scripts
            if what in self.__service2daemon:
                procname, pidfile = self.__service2daemon[what]
                if procname:
                    what = procname
            if action in ("start", "stop", "restart", "reload"):
                if action == 'restart':
                    self._system("/usr/sbin/service " + what + " forcestop ")
                self._system("/usr/sbin/service " + what + " " + action)
                f = self._do_nada
            else:
                raise ValueError("Internal error: Unknown command")
        f()

    __service2daemon = {
        'ctld': ('ctld', '/var/run/ctld.pid'),
        'webshell': (None, '/var/run/webshell.pid'),
        'backup': (None, '/var/run/backup.pid')
    }

    def _started_notify(self, verb, what):
        """
        The check for started [or not] processes is currently done in 2 steps
        This is the first step which involves a thread StartNotify that watch for event
        before actually start/stop rc.d scripts

        Returns:
            StartNotify object if the service is known or None otherwise
        """

        # FIXME: Ugly workaround for one service and multiple backend
        if what == 'iscsitarget':
            what = 'ctld'

        if what in self.__service2daemon:
            procname, pidfile = self.__service2daemon[what]
            sn = StartNotify(verb=verb, pidfile=pidfile)
            sn.start()
            return sn
        else:
            return None

    def _started(self, what, notify=None):
        """
        This is the second step::
        Wait for the StartNotify thread to finish and then check for the
        status of pidfile/procname using pgrep

        Returns:
            True whether the service is alive, False otherwise
        """

        # FIXME: Ugly workaround for one service and multiple backend
        if what == 'iscsitarget':
            what = 'ctld'

        if what in self.__service2daemon:
            procname, pidfile = self.__service2daemon[what]
            if notify:
                notify.join()

            if pidfile:
                procname = " " + procname if procname else ""
                retval = self._pipeopen("/bin/pgrep -F %s%s" % (pidfile, procname)).wait()
            else:
                retval = self._pipeopen("/bin/pgrep %s" % (procname,)).wait()

            if retval == 0:
                return True
            else:
                return False
        else:
            return False

    def init(self, what, objectid=None, *args, **kwargs):
        """ Dedicated command to create "what" designated by an optional objectid.

        The helper will use method self._init_[what]() to create the object"""
        if objectid is None:
            self._simplecmd("init", what)
        else:
            f = getattr(self, '_init_' + what)
            f(objectid, *args, **kwargs)

    def destroy(self, what, objectid=None):
        if objectid is None:
            raise ValueError("Calling destroy without id")
        else:
            f = getattr(self, '_destroy_' + what)
            f(objectid)

    def start(self, what):
        """ Start the service specified by "what".

        The helper will use method self._start_[what]() to start the service.
        If the method does not exist, it would fallback using service(8)."""
        sn = self._started_notify("start", what)
        self._simplecmd("start", what)
        return self.started(what, sn)

    def started(self, what, sn=None):
        """ Test if service specified by "what" has been started. """
        f = getattr(self, '_started_' + what, None)
        if callable(f):
            return f()
        else:
            return self._started(what, sn)

    def stop(self, what):
        """ Stop the service specified by "what".

        The helper will use method self._stop_[what]() to stop the service.
        If the method does not exist, it would fallback using service(8)."""
        sn = self._started_notify("stop", what)
        self._simplecmd("stop", what)
        return self.started(what, sn)

    def restart(self, what):
        """ Restart the service specified by "what".

        The helper will use method self._restart_[what]() to restart the service.
        If the method does not exist, it would fallback using service(8)."""
        sn = self._started_notify("restart", what)
        self._simplecmd("restart", what)
        return self.started(what, sn)

    def reload(self, what):
        """ Reload the service specified by "what".

        The helper will use method self._reload_[what]() to reload the service.
        If the method does not exist, the helper will try self.restart of the
        service instead."""
        try:
            self._simplecmd("reload", what)
        except:
            self.restart(what)
        return self.started(what)

    def change(self, what):
        """ Notify the service specified by "what" about a change.

        The helper will use method self.reload(what) to reload the service.
        If the method does not exist, the helper will try self.start the
        service instead."""
        try:
            self.reload(what)
        except:
            self.start(what)

    def _restart_django(self):
        self._system("/usr/sbin/service django restart")

    def _start_webshell(self):
        self._system_nolog("/usr/local/bin/python /usr/local/www/freenasUI/tools/webshell.py")

    def _start_backup(self):
        self._system_nolog("/usr/local/bin/python /usr/local/www/freenasUI/tools/backup.py")

    def _restart_webshell(self):
        try:
            with open('/var/run/webshell.pid', 'r') as f:
                pid = f.read()
                os.kill(int(pid), signal.SIGHUP)
                time.sleep(0.2)
        except:
            pass
        self._system_nolog("ulimit -n 1024 && /usr/local/bin/python /usr/local/www/freenasUI/tools/webshell.py")

    def _restart_iscsitarget(self):
        self._system("/usr/sbin/service ix-ctld quietstart")
        self._system("/usr/sbin/service ctld forcestop")
        self._system("/usr/sbin/service ctld restart")

    def _start_iscsitarget(self):
        self._system("/usr/sbin/service ix-ctld quietstart")
        self._system("/usr/sbin/service ctld start")

    def _stop_iscsitarget(self):
        self._system("/usr/sbin/service ctld forcestop")

    def _reload_iscsitarget(self):
        self._system("/usr/sbin/service ix-ctld quietstart")
        self._system("/usr/sbin/service ctld reload")

    def _start_sysctl(self):
        self._system("/usr/sbin/service sysctl start")
        self._system("/usr/sbin/service ix-sysctl quietstart")

    def _reload_sysctl(self):
        self._system("/usr/sbin/service sysctl start")
        self._system("/usr/sbin/service ix-sysctl reload")

    def _start_network(self):
        self._system("/usr/sbin/service rtsold stop")
        from freenasUI.network.models import Alias, Interfaces
        qs = Interfaces.objects.filter(int_ipv6auto=True).exists()
        qs2 = Interfaces.objects.exclude(int_ipv6address='').exists()
        qs3 = Alias.objects.exclude(alias_v6address='').exists()
        if qs or qs2 or qs3:
            try:
                auto_linklocal = self.sysctl("net.inet6.ip6.auto_linklocal")
            except AssertionError:
                auto_linklocal = 0
            if auto_linklocal == 0:
                self._system("/sbin/sysctl net.inet6.ip6.auto_linklocal=1")
                self._system("/usr/sbin/service autolink auto_linklocal quietstart")
                self._system("/usr/sbin/service netif stop")
        interfaces = self._pipeopen("ifconfig -l").communicate()[0]
        interface_list = interfaces.split(" ")
        for interface in interface_list:
            if interface.startswith("vlan"):
                self._system("ifconfig %s destroy" % interface)
        self._system("/etc/netstart")
        self._system("/usr/sbin/service rtsold start")

    def _reload_named(self):
        self._system("/usr/sbin/service named reload")

    def _reload_timeservices(self):
        from freenasUI.sysyem.models import Settings
        timezone = Settings.objects.all()[0].stg_timezone
        os.environ['TZ'] = timezone
        time.tzset()

    def _started_nis(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/NIS/ctl status"):
            res = True
        return res

    def _start_nis(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/NIS/ctl start"):
            res = True
        return res

    def _restart_nis(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/NIS/ctl restart"):
            res = True
        return res

    def _stop_nis(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/NIS/ctl stop"):
            res = True
        return res

    def _started_ldap(self):
        from freenasUI.common.freenasldap import FreeNAS_LDAP, FLAGS_DBINIT
        from freenasUI.common.system import ldap_enabled

        if (self._system_nolog('/usr/sbin/service ix-ldap status') != 0):
            return False

        ret = False
        try:
            f = FreeNAS_LDAP(flags=FLAGS_DBINIT)
            f.open()
            if f.isOpen():
                ret = True
            f.close()
        except:
            pass

        return ret

    def _start_ldap(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/LDAP/ctl start"):
            res = True
        return res

    def _stop_ldap(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/LDAP/ctl stop"):
            res = True
        return res

    def _restart_ldap(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/LDAP/ctl restart"):
            res = True
        return res

    def _clear_activedirectory_config(self):
        self._system("/bin/rm -f /etc/directoryservice/ActiveDirectory/config")

    def _started_nt4(self):
        res = False
        ret = self._system_nolog("service ix-nt4 status")
        if not ret:
            res = True
        return res

    def _start_nt4(self):
        res = False
        ret = self._system_nolog("/etc/directoryservice/NT4/ctl start")
        if not ret:
            res = True
        return res

    def _restart_nt4(self):
        res = False
        ret = self._system_nolog("/etc/directoryservice/NT4/ctl restart")
        if not ret:
            res = True
        return res

    def _stop_nt4(self):
        res = False
        ret = self._system_nolog("/etc/directoryservice/NT4/ctl stop")
        return res

    def _started_activedirectory(self):
        from freenasUI.common.freenasldap import (FreeNAS_ActiveDirectory, FLAGS_DBINIT)
        from freenasUI.common.system import activedirectory_enabled

        for srv in ('kinit', 'activedirectory', ):
            if (self._system_nolog('/usr/sbin/service ix-%s status' % (srv, ))
                != 0):
                return False

        ret = False
        try:
            f = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
            if f.connected():
                ret = True
        except:
            pass

        return ret

    def _start_activedirectory(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/ActiveDirectory/ctl start"):
            res = True
        return res

    def _stop_activedirectory(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/ActiveDirectory/ctl stop"):
            res = True
        return res

    def _restart_activedirectory(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/ActiveDirectory/ctl restart"):
            res = True
        return res

    def _started_domaincontroller(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/DomainController/ctl status"):
            res = True
        return res

    def _start_domaincontroller(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/DomainController/ctl start"):
            res = True
        return res

    def _stop_domaincontroller(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/DomainController/ctl stop"):
            res = True
        return res

    def _restart_domaincontroller(self):
        res = False
        if not self._system_nolog("/etc/directoryservice/DomainController/ctl restart"):
            res = True
        return res

    def _restart_cron(self):
        self._system("/usr/sbin/service ix-crontab quietstart")

    def start_ataidle(self, what=None):
        if what is not None:
            self._system("/usr/sbin/service ix-ataidle quietstart %s" % what)
        else:
            self._system("/usr/sbin/service ix-ataidle quietstart")

    def start_ssl(self, what=None):
        if what is not None:
            self._system("/usr/sbin/service ix-ssl quietstart %s" % what)
        else:
            self._system("/usr/sbin/service ix-ssl quietstart")

    def _restart_system(self):
        self._system("/bin/sleep 3 && /sbin/shutdown -r now &")

    def _stop_system(self):
        self._system("/sbin/shutdown -p now")

    def _restart_http(self):
        self._system("/usr/sbin/service ix_register reload")
        self._system("/usr/sbin/service nginx restart")

    def _reload_http(self):
        self._system("/usr/sbin/service ix_register reload")
        self._system("/usr/sbin/service nginx reload")

    def _open_db(self, ret_conn=False):
        """Open and return a cursor object for database access."""
        try:
            from freenasUI.settings import DATABASES
            dbname = DATABASES['default']['NAME']
        except:
            dbname = '/data/freenas-v1.db'

        conn = sqlite3.connect(dbname)
        c = conn.cursor()
        if ret_conn:
            return c, conn
        return c

    def get_swapsize(self):
        from freenasUI.system.models import Advanced
        swapsize = Advanced.objects.latest('id').adv_swapondrive
        return swapsize

    def list_zfs_vols(self, volname, sort=None):
        """Return a dictionary that contains all ZFS volumes list"""

        from freenasUI.middleware.connector import connection as dispatcher
        result = dispatcher.call_sync('zfs.dataset.query', [
            ('type', '=', 'volume'),
            ('pool', '=', volname)
        ], {'sort': sort} if sort else None)

        return {i['name']: i for i in result}

    def list_zfs_fsvols(self, system=False):
        from freenasUI.middleware.connector import connection as dispatcher
        if system:
            result = dispatcher.call_sync('zfs.dataset.query', [('name', '~', '\.system')])
        else:
            result = dispatcher.call_sync('zfs.dataset.query')

        return {i['name']: i for i in result}

    def __snapshot_hold(self, name):
        """
        Check if a given snapshot is being hold by the replication system
        DISCLAIMER: mntlock has to be acquired before this call
        """
        zfsproc = self._pipeopen("zfs get -H freenas:state '%s'" % (name))
        output = zfsproc.communicate()[0]
        if output != '':
            fsname, attrname, value, source = output.split('\n')[0].split('\t')
            if value != '-' and value != 'NEW':
                return True
        return False

    def repl_remote_snapshots(self, repl):
        """
        Get a list of snapshots in the remote side
        """
        if repl.repl_remote.ssh_remote_dedicateduser_enabled:
            user = repl.repl_remote.ssh_remote_dedicateduser
        else:
            user = 'root'
        proc = self._pipeopen('/usr/bin/ssh -i /data/ssh/replication -o ConnectTimeout=3 -p %s "%s"@"%s" "zfs list -Ht snapshot -o name"' % (
            repl.repl_remote.ssh_remote_port,
            user,
            repl.repl_remote.ssh_remote_hostname,
        ))
        data = proc.communicate()[0]
        if proc.returncode != 0:
            return []
        return data.strip('\n').split('\n')

    def __get_mountpath(self, name, fstype, mountpoint_root='/mnt'):
        """Determine the mountpoint for a volume or ZFS dataset

        It tries to divine the location of the volume or dataset from the
        relevant command, and if all else fails, falls back to a less
        elegant method of representing the mountpoint path.

        This is done to ensure that in the event that the database and
        reality get out of synch, the user can nuke the volume/mountpoint.

        XXX: this should be done more elegantly by calling getfsent from C.

        Required Parameters:
            name: textual name for the mountable vdev or volume, e.g. 'tank',
                  'stripe', 'tank/dataset', etc.
            fstype: filesystem type for the vdev or volume, e.g. 'UFS', 'ZFS',
                    etc.

        Optional Parameters:
            mountpoint_root: the root directory where all of the datasets and
                             volumes shall be mounted. Defaults to '/mnt'.

        Returns:
            the absolute path for the volume on the system.
        """
        if fstype == 'ZFS':
            p1 = self._pipeopen("zfs list -H -o mountpoint '%s'" % (name, ))
            stdout = p1.communicate()[0]
            if not p1.returncode:
                return stdout.strip()
        elif fstype == 'UFS':
            p1 = self._pipeopen('mount -p')
            stdout = p1.communicate()[0]
            if not p1.returncode:
                flines = filter(lambda x: x and x.split()[0] ==
                                                '/dev/ufs/' + name,
                                stdout.splitlines())
                if flines:
                    return flines[0].split()[1]

        return os.path.join(mountpoint_root, name)

    def _reload_disk(self):
        self._system("/usr/sbin/service ix-fstab quietstart")
        self._system("/usr/sbin/service ix-swap quietstart")
        self._system("/usr/sbin/service swap quietstart")
        self._system("/usr/sbin/service mountlate quietstart")
        self.restart("collectd")
        self.__confxml = None

    # Create a user in system then samba
    def __pw_with_password(self, command, password):
        pw = self._pipeopen(command)
        msg = pw.communicate("%s\n" % password)[1]
        if pw.returncode != 0:
            raise MiddlewareError("Operation could not be performed. %s" % msg)

        if msg != "":
            log.debug("Command reports %s", msg)

    def __smbpasswd(self, username, password):
        """
        Add the user ``username'' to samba using ``password'' as
        the current password

        Returns:
            True whether the user has been successfully added and False otherwise
        """

        # For domaincontroller mode, rely on RSAT for user modification
        if domaincontroller_enabled():
            return 0

        command = '/usr/local/bin/smbpasswd -D 0 -s -a "%s"' % (username)
        smbpasswd = self._pipeopen(command)
        smbpasswd.communicate("%s\n%s\n" % (password, password))
        return smbpasswd.returncode == 0

    def __issue_pwdchange(self, username, command, password):
        self.__pw_with_password(command, password)
        self.__smbpasswd(username, password)

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
            unixgroup.encode('utf8'),
            ntgroup.encode('utf8')
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

    def user_changepassword(self, username, password):
        """Changes user password"""
        command = '/usr/sbin/pw usermod "%s" -h 0' % (username)
        self.__issue_pwdchange(username, command, password)
        return self.user_gethashedpassword(username)

    def user_gethashedpassword(self, username):
        """
        Get the samba hashed password for ``username''

        Returns:
            tuple -> (user password, samba hash)
        """

        """
        Make sure to use -d 0 for pdbedit, otherwise it will bomb
        if CIFS debug level is anything different than 'Minimum'
        """
        smb_command = "/usr/local/bin/pdbedit -d 0 -w %s" % username
        smb_cmd = self._pipeopen(smb_command)
        smb_hash = smb_cmd.communicate()[0].split('\n')[0]
        user = self.___getpwnam(username)
        return (user.pw_passwd, smb_hash)

    def _reload_user(self):
        self.reload("cifs")

    def mp_get_permission(self, path):
        if os.path.isdir(path):
            return stat.S_IMODE(os.stat(path)[stat.ST_MODE])

    def mp_get_owner(self, path):
        """Gets the owner/group for a given mountpoint.

        Defaults to root:wheel if the owner of the mountpoint cannot be found.

        XXX: defaulting to root:wheel is wrong if the users/groups are out of
             synch with the remote hosts. These cases should really raise
             Exceptions and be handled differently in the GUI.

        Raises:
            OSError - the path provided isn't a directory.
        """
        if os.path.isdir(path):
            stat_info = os.stat(path)
            uid = stat_info.st_uid
            gid = stat_info.st_gid
            try:
                pw = pwd.getpwuid(uid)
                user = pw.pw_name
            except KeyError:
                user = 'root'
            try:
                gr = grp.getgrgid(gid)
                group = gr.gr_name
            except KeyError:
                group = 'wheel'
            return (user, group, )
        raise OSError('Invalid mountpoint %s' % (path, ))

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
            "provider[name = 'ufs/%s']/../consumer/provider/@ref" % (label, )
        )
        #prov = doc.xpathEval("//provider[@id = '%s']" % pref[0].content)
        if not pref:
            proc = self._pipeopen("/sbin/mdconfig -a -t swap -s 2800m")
            mddev, err = proc.communicate()
            if proc.returncode != 0:
                raise MiddlewareError("Could not create memory device: %s" % err)

            proc = self._pipeopen("newfs -L %s /dev/%s" % (label, mddev))
            err = proc.communicate()[1]
            if proc.returncode != 0:
                raise MiddlewareError("Could not create temporary filesystem: %s" % err)

            self._system("/bin/rm -rf /var/tmp/firmware")
            self._system("/bin/mkdir -p /var/tmp/firmware")
            proc = self._pipeopen("mount /dev/ufs/%s /var/tmp/firmware" % (label, ))
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
            "provider[name = 'ufs/%s']/../consumer/provider/@ref" % (label, )
        )
        if not pref:
            return False
        prov = doc.xpath("//class[name = 'MD']//provider[@id = '%s']/name" % pref[0])
        if not prov:
            return False

        mddev = prov[0].text

        self._system("umount /dev/ufs/%s" % (label, ))
        proc = self._pipeopen("mdconfig -d -u %s" % (mddev, ))
        err = proc.communicate()[1]
        if proc.returncode != 0:
            raise MiddlewareError("Could not destroy memory device: %s" % err)

        return True

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

    def checksum(self, path, algorithm='sha256'):
        algorithm2map = {
            'sha256': '/sbin/sha256 -q',
        }
        hasher = self._pipeopen('%s %s' % (algorithm2map[algorithm], path))
        sum = hasher.communicate()[0].split('\n')[0]
        return sum

    def get_disks(self):
        """
        Grab usable disks and pertinent info about them
        This accounts for:
            - all the disks the OS found
                (except the ones that are providers for multipath)
            - multipath geoms providers

        Returns:
            Dict of disks
        """
        from freenasUI.middleware.connector import connection as dispatcher
        disks = dispatcher.call_sync('disks.query')

        def convert(disk):
            return {
                'devname': disk['path'],
                'capacity': disk['mediasize'],
                'ident': disk['lunid']
            }

        return {d['path']: convert(d) for d in disks}

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

    def zfs_import(self, name, id=None):
        if id is not None:
            imp = self._pipeopen('zpool import -f -R /mnt %s' % id)
        else:
            imp = self._pipeopen('zpool import -f -R /mnt %s' % name)
        stdout, stderr = imp.communicate()
        if imp.returncode == 0:
            # Reset all mountpoints in the zpool
            self.zfs_inherit_option(name, 'mountpoint', True)
            # Remember the pool cache
            self._system("zpool set cachefile=/data/zfs/zpool.cache %s" % (name))
            # These should probably be options that are configurable from the GUI
            self._system("zfs set aclmode=passthrough '%s'" % name)
            self._system("zfs set aclinherit=passthrough '%s'" % name)
            self.restart("collectd")
            return True
        else:
            log.error("Importing %s [%s] failed with: %s",
                name,
                id,
                stderr)
        return False

    def zfs_snapshot_list(self, path=None, replications=None, sort=None, system=False):
        from freenasUI.storage.models import Volume
        fsinfo = dict()

        if sort is None:
            sort = ''
        else:
            sort = '-s %s' % sort

        if system is False:
            #FIXME
            #systemdataset, basename = self.system_dataset_settings()
            systemdataset, basename = None, None


        zfsproc = self._pipeopen("/sbin/zfs list -t volume -o name %s -H" % sort)
        zvols = filter(lambda y: y != '', zfsproc.communicate()[0].split('\n'))

        volnames = [
            o.vol_name for o in Volume.objects.filter(vol_fstype='ZFS')
        ]

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
                except:
                    snaplist = []
                    mostrecent = True
                replication = None
                if replications:
                    for repl, snaps in replications.iteritems():
                        if fs != repl.repl_filesystem:
                            break
                        remotename = '%s@%s' % (
                            repl.repl_zfs,
                            name,
                        )
                        if remotename in snaps:
                            replication = 'OK'
                            # TODO: Multiple replication tasks
                            break

                snaplist.insert(0,
                    zfs.Snapshot(
                        name=name,
                        filesystem=fs,
                        used=used,
                        refer=refer,
                        mostrecent=mostrecent,
                        parent_type='filesystem' if fs not in zvols else 'volume',
                        replication=replication,
                        vmsynced=(vmsynced == 'Y')
                    ))
                fsinfo[fs] = snaplist
        return fsinfo

    def zfs_mksnap(self, dataset, name, recursive=False, vmsnaps_count=0):
        if vmsnaps_count > 0:
            vmflag = '-o freenas:vmsynced=Y '
        else:
            vmflag = ''
        if recursive:
            p1 = self._pipeopen("/sbin/zfs snapshot -r %s '%s'@'%s'" % (vmflag, dataset, name))
        else:
            p1 = self._pipeopen("/sbin/zfs snapshot %s '%s'@'%s'" % (vmflag, dataset, name))
        if p1.wait() != 0:
            err = p1.communicate()[1]
            raise MiddlewareError("Snapshot could not be taken: %s" % err)
        return True

    def zfs_clonesnap(self, snapshot, dataset):
        zfsproc = self._pipeopen("zfs clone '%s' '%s'" % (snapshot, dataset))
        retval = zfsproc.communicate()[1]
        return retval

    def rollback_zfs_snapshot(self, snapshot):
        zfsproc = self._pipeopen("zfs rollback '%s'" % (snapshot))
        retval = zfsproc.communicate()[1]
        return retval

    def config_restore(self):
        os.unlink("/data/freenas-v1.db")
        save_path = os.getcwd()
        os.chdir(FREENAS_PATH)
        self._system("/usr/local/bin/python manage.py syncdb --noinput --migrate")
        self._system("/usr/local/bin/python manage.py createadmin")
        os.chdir(save_path)

    def config_upload(self, uploaded_file_fd):
        config_file_name = tempfile.mktemp(dir='/var/tmp/firmware')
        try:
            with open(config_file_name, 'wb') as config_file_fd:
                for chunk in uploaded_file_fd.chunks():
                    config_file_fd.write(chunk)
            conn = sqlite3.connect(config_file_name)
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM south_migrationhistory")
                new_num = cur.fetchone()[0]
                cur.close()
            finally:
                conn.close()
            conn = sqlite3.connect(FREENAS_DATABASE)
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM south_migrationhistory")
                num = cur.fetchone()[0]
                cur.close()
            finally:
                conn.close()
                if new_num > num:
                    return False, _(
                        "Failed to upload config, version newer than the "
                        "current installed."
                    )
        except:
            os.unlink(config_file_name)
            return False, _('The uploaded file is not valid.')

        shutil.move(config_file_name, '/data/uploaded.db')
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
        value = str(value)
        if recursive:
            zfsproc = self._pipeopen("zfs set -r '%s'='%s' '%s'" % (item, value, name))
        else:
            zfsproc = self._pipeopen("zfs set '%s'='%s' '%s'" % (item, value, name))
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

    def __init__(self):
        self.__confxml = None
        self.__camcontrol = None
        self.__diskserial = {}
        self.__twcli = {}

    def __del__(self):
        self.__confxml = None

    def _geom_confxml(self):
        from lxml import etree
        if self.__confxml is None:
            self.__confxml = etree.fromstring(self.sysctl('kern.geom.confxml'))
        return self.__confxml

    def __get_twcli(self, controller):
        if controller in self.__twcli:
            return self.__twcli[controller]

        re_port = re.compile(r'^p(?P<port>\d+).*?\bu(?P<unit>\d+)\b', re.S | re.M)
        proc = self._pipeopen("/usr/local/sbin/tw_cli /c%d show" % (controller, ))
        output = proc.communicate()[0]

        units = {}
        for port, unit in re_port.findall(output):
            units[int(unit)] = int(port)

        self.__twcli[controller] = units
        return self.__twcli[controller]

    def get_smartctl_args(self, devname):
        args = ["/dev/%s" % devname]
        camcontrol = self._camcontrol_list()
        info = camcontrol.get(devname)
        if info is not None:
            if info.get("drv") == "rr274x_3x":
                channel = info["channel"] + 1
                if channel > 16:
                    channel -= 16
                elif channel > 8:
                    channel -= 8
                args = [
                    "/dev/%s" % info["drv"],
                    "-d",
                    "hpt,%d/%d" % (info["controller"] + 1, channel)
                    ]
            elif info.get("drv").startswith("arcmsr"):
                args = [
                    "/dev/%s%d" % (info["drv"], info["controller"]),
                    "-d",
                    "areca,%d" % (info["lun"] + 1 + (info["channel"] * 8), )
                    ]
            elif info.get("drv").startswith("hpt"):
                args = [
                    "/dev/%s" % info["drv"],
                    "-d",
                    "hpt,%d/%d" % (info["controller"] + 1, info["channel"] + 1)
                    ]
            elif info.get("drv") == "ciss":
                args = [
                    "/dev/%s%d" % (info["drv"], info["controller"]),
                    "-d",
                    "cciss,%d" % (info["channel"], )
                    ]
            elif info.get("drv") == "twa":
                twcli = self.__get_twcli(info["controller"])
                args = [
                    "/dev/%s%d" % (info["drv"], info["controller"]),
                    "-d",
                    "3ware,%d" % (twcli.get(info["channel"], -1), )
                    ]
        return args

    def get_label_consumer(self, geom, name):
        """
        Get the label consumer of a given ``geom`` with name ``name``

        Returns:
            The provider xmlnode if found, None otherwise
        """
        doc = self._geom_confxml()
        xpath = doc.xpath("//class[name = 'LABEL']//provider[name = '%s']/../consumer/provider/@ref" % "%s/%s" % (geom, name))
        if not xpath:
            return None
        providerid = xpath[0]
        provider = doc.xpath("//provider[@id = '%s']" % providerid)[0]

        class_name = provider.xpath("../../name")[0].text

        # We've got a GPT over the softraid, not raw UFS filesystem
        # So we need to recurse one more time
        if class_name == 'PART':
            providerid = provider.xpath("../consumer/provider/@ref")[0]
            newprovider = doc.xpath("//provider[@id = '%s']" % providerid)[0]
            class_name = newprovider.xpath("../../name")[0].text
            # if this PART is really backed up by softraid the hypothesis was correct
            if class_name in ('STRIPE', 'MIRROR', 'RAID3'):
                return newprovider

        return provider

    def get_disks_from_provider(self, provider):
        disks = []
        geomname = provider.xpath("../../name")[0].text
        if geomname in ('DISK', 'PART'):
            disks.append(provider.xpath("../name")[0].text)
        elif geomname in ('STRIPE', 'MIRROR', 'RAID3'):
            doc = self._geom_confxml()
            for prov in provider.xpath("../consumer/provider/@ref"):
                prov2 = doc.xpath("//provider[@id = '%s']" % prov)[0]
                disks.append(prov2.xpath("../name")[0].text)
        else:
            # TODO log, could not get disks
            pass
        return disks

    def zpool_parse(self, name):
        doc = self._geom_confxml()
        p1 = self._pipeopen("zpool status %s" % name)
        res = p1.communicate()[0]
        parse = zfs.parse_status(name, doc, res)
        return parse

    def _find_root_devs(self):
        """Find the root device.

        Returns:
             The root device name in string format

        """

        try:
            zpool = self.zpool_parse('freenas-boot')
            return zpool.get_disks()
        except:
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

        return filter(lambda x: not device_blacklist_re.match(x) and x not in blacklist_devs, disks)

    def retaste_disks(self):
        """
        Retaste disks for GEOM metadata

        This will not work if the device is already open

        It is useful in multipath situations, for example.
        """
        disks = self.__get_disks()
        for disk in disks:
            open("/dev/%s" % disk, 'w').close()

    def kern_module_is_loaded(self, module):
        """Determine whether or not a kernel module (or modules) is loaded.

        Parameter:
            module_name - a module to look for in kldstat -v output (.ko is
                          added automatically for you).

        Returns:
            A boolean to denote whether or not the module was found.
        """

        pipe = self._pipeopen('/sbin/kldstat -v')

        return 0 < pipe.communicate()[0].find(module + '.ko')

    def sysctl(self, name):
        """
        Tiny wrapper for sysctl module for compatibility
        """
        sysc = sysctl.sysctlbyname(name)
        if sysc is not None:
            return sysc
            
        raise ValueError(name)

    def mount_volume(self, volume):
        """
        Mount a volume.
        The volume must be in /etc/fstab

        Returns:
            True if volume was sucessfully mounted, False otherwise
        """
        if volume.vol_fstype == 'ZFS':
            raise NotImplementedError("No donuts for you!")

        prov = self.get_label_consumer(volume.vol_fstype.lower(),
            str(volume.vol_name))
        if prov is None:
            return False

        proc = self._pipeopen("mount /dev/%s/%s" % (
            volume.vol_fstype.lower(),
            volume.vol_name,
            ))
        if proc.wait() != 0:
            return False
        return True

    def __get_geoms_recursive(self, prvid):
        """
        Get _ALL_ geom nodes that depends on a given provider
        """
        doc = self._geom_confxml()
        geoms = []
        for c in doc.xpath("//consumer/provider[@ref = '%s']" % (prvid, )):
            geom = c.getparent().getparent()
            if geom.tag != 'geom':
                continue
            geoms.append(geom)
            for prov in geom.xpath('./provider'):
                geoms.extend(self.__get_geoms_recursive(prov.attrib.get('id')))

        return geoms

    def disk_get_consumers(self, devname):
        doc = self._geom_confxml()
        geom = doc.xpath("//class[name = 'DISK']/geom[name = '%s']" % (
            devname,
        ))
        if geom:
            provid = geom[0].xpath("./provider/@id")[0]
        else:
            raise ValueError("Unknown disk %s" % (devname, ))
        return self.__get_geoms_recursive(provid)

    def _do_disk_wipe_quick(self, devname):
        pipe = self._pipeopen("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (devname, ))
        err = pipe.communicate()[1]
        if pipe.returncode != 0:
            raise MiddlewareError(
                "Failed to wipe %s: %s" % (devname, err)
            )
        try:
            p1 = self._pipeopen("diskinfo %s" % (devname, ))
            size = int(re.sub(r'\s+', ' ', p1.communicate()[0]).split()[2]) / (1024)
        except:
            log.error("Unable to determine size of %s", devname)
        else:
            pipe = self._pipeopen("dd if=/dev/zero of=/dev/%s bs=1m oseek=%s" % (
                devname,
                size / 1024 - 4,
            ))
            pipe.communicate()

    def disk_wipe(self, devname, mode='quick'):
        if mode == 'quick':
            doc = self._geom_confxml()
            parts = [node.text for node in doc.xpath("//class[name = 'PART']/geom[name = '%s']/provider/name" % devname)]
            """
            Wipe beginning and the end of every partition
            This should erase ZFS label and such to prevent further errors on replace
            """
            for part in parts:
                self._do_disk_wipe_quick(part)
            self.__gpt_unlabeldisk(devname)
            self._do_disk_wipe_quick(devname)

        elif mode in ('full', 'fullrandom'):
            libc = ctypes.cdll.LoadLibrary("libc.so.7")
            omask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
            mask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
            pmask = ctypes.pointer(mask)
            pomask = ctypes.pointer(omask)
            libc.sigprocmask(signal.SIGQUIT, pmask, pomask)

            self.__gpt_unlabeldisk(devname)
            stderr = open('/var/tmp/disk_wipe_%s.progress' % (devname, ), 'w+')
            stderr.flush()
            pipe = subprocess.Popen([
                "dd",
                "if=/dev/zero" if mode == 'full' else "if=/dev/random",
                "of=/dev/%s" % (devname, ),
                "bs=1m",
                ],
                stdout=subprocess.PIPE,
                stderr=stderr,
                )
            with open('/var/tmp/disk_wipe_%s.pid' % (devname, ), 'w') as f:
                f.write(str(pipe.pid))
            pipe.communicate()
            stderr.seek(0)
            err = stderr.read()
            libc.sigprocmask(signal.SIGQUIT, pomask, None)
            if pipe.returncode != 0 and err.find("end of device") == -1:
                raise MiddlewareError(
                    "Failed to wipe %s: %s" % (devname, err)
                    )
        else:
            raise ValueError("Unknown mode %s" % (mode, ))

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

    def get_proc_title(self, pid):
        proc = self._pipeopen('/bin/ps -a -x -w -w -o pid,command | /usr/bin/grep ^%s' % pid)
        data = proc.communicate()[0]
        if proc.returncode != 0:
            return None
        data = data.strip('\n')
        title = data.split(' ', 1)
        if len(title) > 1:
            return title[1]
        else:
            return False

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

    def get_dataset_aclmode(self, dataset):
        aclmode = None
        if not dataset:
            return aclmode

        proc = self._pipeopen('/sbin/zfs get -H -o value aclmode "%s"' % dataset)
        stdout, stderr = proc.communicate()
        if proc.returncode == 0:
            aclmode = stdout.strip()

        return aclmode

    def set_dataset_aclmode(self, dataset, aclmode):
        if not dataset or not aclmode:
            return False

        proc = self._pipeopen('/sbin/zfs set aclmode="%s" "%s"' % (aclmode, dataset))
        if proc.returncode != 0:
            return False

        return True

    def _createlink(self, syspath, item):
        if not os.path.isfile(os.path.join(syspath, os.path.basename(item))):
            if os.path.exists(os.path.join(syspath, os.path.basename(item))):
                # There's something here but it's not a file.
                shutil.rmtree(os.path.join(syspath, os.path.basename(item)))
            open(os.path.join(syspath, os.path.basename(item)), "w").close()
        os.symlink(os.path.join(syspath, os.path.basename(item)), item)

    def nfsv4link(self):
        syspath = self.system_dataset_path()
        if not syspath:
            return None

        restartfiles = ["/var/db/nfs-stablerestart", "/var/db/nfs-stablerestart.bak"]
        if (
            hasattr(self, 'failover_status') and
            self.failover_status() == 'BACKUP'
        ):
            return None

        for item in restartfiles:
            if os.path.exists(item):
                if os.path.isfile(item) and not os.path.islink(item):
                    # It's an honest to goodness file, this shouldn't ever happen...but
                    if not os.path.isfile(os.path.join(syspath, os.path.basename(item))):
                        # there's no file in the system dataset, so copy over what we have
                        # being careful to nuke anything that is there that happens to
                        # have the same name.
                        if os.path.exists(os.path.join(syspath, os.path.basename(item))):
                            shutil.rmtree(os.path.join(syspath, os.path.basename(item)))
                        shutil.copy(item, os.path.join(syspath, os.path.basename(item)))
                    # Nuke the original file and create a symlink to it
                    # We don't need to worry about creating the file on the system dataset
                    # because it's either been copied over, or was already there.
                    os.unlink(item)
                    os.symlink(os.path.join(syspath, os.path.basename(item)), item)
                elif os.path.isdir(item):
                    # Pathological case that should never happen
                    shutil.rmtree(item)
                    self._createlink(syspath, item)
                else:
                    if not os.path.exists(os.readlink(item)):
                        # Dead symlink or some other nastiness.
                        shutil.rmtree(item)
                        self._createlink(syspath, item)
            else:
                # We can get here if item is a dead symlink
                if os.path.islink(item):
                    os.unlink(item)
                self._createlink(syspath, item)

    def zpool_status(self,pool_name):
        """
        Function to find out the status of the zpool
        It takes the name of the zpool (as a string) as the
        argument. It returns with a tuple of (state, status)
        """
        status = ''
        state = ''
        p1 = self._pipeopen("/sbin/zpool status -x %s" % pool_name)
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
            #action = ""
            #reg2 = re.search(r'^\s*action: ([^:]+)\n\s*\w+:',
                             #zpool_result, re.S | re.M)
            #if reg2:
                #msg = reg2.group(1)
                #action = re.sub(r'\s+', ' ', msg)
        return (state, status)

    def pwenc_reset_model_passwd(self, model, field):
        for obj in model.objects.all():
            setattr(obj, field, '')
            obj.save()

    def pwenc_generate_secret(self, reset_passwords=True, _settings=None):
        from Crypto import Random
        if _settings is None:
            from freenasUI.system.models import Settings
            _settings = Settings

        try:
            settings = _settings.objects.order_by('-id')[0]
        except IndexError:
            settings = _settings.objects.create()

        secret = Random.new().read(PWENC_BLOCK_SIZE)
        with open(PWENC_FILE_SECRET, 'wb') as f:
            os.chmod(PWENC_FILE_SECRET, 0600)
            f.write(secret)

        settings.stg_pwenc_check = self.pwenc_encrypt(PWENC_CHECK)
        settings.save()

        if reset_passwords:
            from freenasUI.directoryservice.models import ActiveDirectory, LDAP, NT4
            self.pwenc_reset_model_passwd(ActiveDirectory, 'ad_bindpw')
            self.pwenc_reset_model_passwd(LDAP, 'ldap_bindpw')
            self.pwenc_reset_model_passwd(NT4, 'nt4_adminpw')

    def pwenc_check(self):
        from freenasUI.system.models import Settings
        try:
            settings = Settings.objects.order_by('-id')[0]
        except IndexError:
            settings = Settings.objects.create()
        try:
            return self.pwenc_decrypt(settings.stg_pwenc_check) == PWENC_CHECK
        except IOError:
            return False

    def pwenc_get_secret(self):
        with open(PWENC_FILE_SECRET, 'rb') as f:
            secret = f.read()
        return secret

    def pwenc_encrypt(self, text):
        from Crypto.Random import get_random_bytes
        from Crypto.Util import Counter
        pad = lambda x: x + (PWENC_BLOCK_SIZE - len(x) % PWENC_BLOCK_SIZE) * PWENC_PADDING

        nonce = get_random_bytes(8)
        cipher = AES.new(
            self.pwenc_get_secret(),
            AES.MODE_CTR,
            counter=Counter.new(64, prefix=nonce),
        )
        encoded = base64.b64encode(nonce + cipher.encrypt(pad(text)))
        return encoded

    def pwenc_decrypt(self, encrypted=None):
        if not encrypted:
            return ""
        from Crypto.Util import Counter
        encrypted = base64.b64decode(encrypted)
        nonce = encrypted[:8]
        encrypted = encrypted[8:]
        cipher = AES.new(
            self.pwenc_get_secret(),
            AES.MODE_CTR,
            counter=Counter.new(64, prefix=nonce),
        )
        return cipher.decrypt(encrypted).rstrip(PWENC_PADDING)

    def bootenv_attach_disk(self, label, devname):
        """Attach a new disk to the pool"""

        self._system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (devname, ))
        try:
            p1 = self._pipeopen("diskinfo %s" % (devname, ))
            size = int(re.sub(r'\s+', ' ', p1.communicate()[0]).split()[2]) / (1024)
        except:
            log.error("Unable to determine size of %s", devname)
        else:
            # HACK: force the wipe at the end of the disk to always succeed. This # is a lame workaround.
            self._system("dd if=/dev/zero of=/dev/%s bs=1m oseek=%s" % (
                devname,
                size / 1024 - 4,
                ))

        commands = []
        commands.append("gpart create -s gpt /dev/%s" % (devname, ))
        commands.append("gpart add -t bios-boot -i 1 -s 512k %s" % devname)
        commands.append("gpart add -t freebsd-zfs -i 2 -a 4k %s" % devname)
        commands.append("gpart set -a active %s" % devname)

        for command in commands:
            proc = self._pipeopen(command)
            proc.wait()
            if proc.returncode != 0:
                raise MiddlewareError('Unable to GPT format the disk "%s"' % devname)

        proc = self._pipeopen('/sbin/zpool attach freenas-boot %s %sp2' % (label, devname))
        err = proc.communicate()[1]
        if proc.returncode != 0:
            raise MiddlewareError('Failed to attach disk: %s' % err)

        time.sleep(10)
        self._system("/usr/local/sbin/grub-install --modules='zfs part_gpt' /dev/%s" % devname)

        return True

    def bootenv_replace_disk(self, label, devname):
        """Attach a new disk to the pool"""

        self._system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (devname, ))
        try:
            p1 = self._pipeopen("diskinfo %s" % (devname, ))
            size = int(re.sub(r'\s+', ' ', p1.communicate()[0]).split()[2]) / (1024)
        except:
            log.error("Unable to determine size of %s", devname)
        else:
            # HACK: force the wipe at the end of the disk to always succeed. This # is a lame workaround.
            self._system("dd if=/dev/zero of=/dev/%s bs=1m oseek=%s" % (
                devname,
                size / 1024 - 4,
                ))

        commands = []
        commands.append("gpart create -s gpt /dev/%s" % (devname, ))
        commands.append("gpart add -t bios-boot -i 1 -s 512k %s" % devname)
        commands.append("gpart add -t freebsd-zfs -i 2 -a 4k %s" % devname)
        commands.append("gpart set -a active %s" % devname)

        for command in commands:
            proc = self._pipeopen(command)
            proc.wait()
            if proc.returncode != 0:
                raise MiddlewareError('Unable to GPT format the disk "%s"' % devname)

        proc = self._pipeopen('/sbin/zpool replace freenas-boot %s %sp2' % (label, devname))
        err = proc.communicate()[1]
        if proc.returncode != 0:
            raise MiddlewareError('Failed to attach disk: %s' % err)

        time.sleep(10)
        self._system("/usr/local/sbin/grub-install --modules='zfs part_gpt' /dev/%s" % devname)

        return True

    def iscsi_active_connections(self):
        from lxml import etree
        proc = self._pipeopen('ctladm islist -x')
        xml = proc.communicate()[0]
        xml = etree.fromstring(xml)
        connections = xml.xpath('//connection')
        return len(connections)

    def call_backupd(self, args):
        ntries = 15
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        # Try for a while in case daemon is just starting
        while ntries > 0:
            try:
                sock.connect(BACKUP_SOCK)
                break
            except socket.error:
                ntries -= 1
                time.sleep(1)

        if ntries == 0:
            # Mark backup as failed at this point
            from freenasUI.system.models import Backup
            backup = Backup.objects.all().order_by('-id').first()
            backup.bak_failed = True
            backup.bak_status = 'Backup process died'
            backup.save()
            return {'status': 'ERROR'}

        sock.settimeout(5)
        f = sock.makefile(bufsize=0)

        try:
            f.write(json.dumps(args) + '\n')
            resp_json = f.readline()
            response = json.loads(resp_json)
        except (IOError, ValueError, socket.timeout):
            # Mark backup as failed at this point
            from freenasUI.system.models import Backup
            backup = Backup.objects.all().order_by('-id').first()
            backup.bak_failed = True
            backup.bak_status = 'Backup process died'
            backup.save()
            response = {'status': 'ERROR'}

        f.close()
        sock.close()
        return response

    def backup_db(self):
        pass


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
        print f(*sys.argv[2:])
