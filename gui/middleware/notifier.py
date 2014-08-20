#!/usr/bin/env python
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

from collections import defaultdict, OrderedDict
from decimal import Decimal
import ctypes
import errno
import glob
import grp
import json
import logging
from lxml import etree
import os
import pipes
import platform
import pwd
import re
import select
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
SYSTEMPATH = '/var/db/system'
BACKUP_SOCK = '/var/run/backupd.sock'

sys.path.append(WWW_PATH)
sys.path.append(FREENAS_PATH)

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

from django.db.models import Q

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from django.utils.translation import ugettext as _

from freenasUI.common.acl import ACL_FLAGS_OS_WINDOWS, ACL_WINDOWS_FILE
from freenasUI.common.freenasacl import ACL
from freenasUI.common.jail import Jls, Jexec
from freenasUI.common.locks import mntlock
from freenasUI.common.pbi import (
    pbi_add, pbi_delete, pbi_info, pbi_create, pbi_makepatch, pbi_patch,
    PBI_ADD_FLAGS_NOCHECKSIG, PBI_ADD_FLAGS_INFO,
    PBI_ADD_FLAGS_FORCE,
    PBI_INFO_FLAGS_VERBOSE, PBI_CREATE_FLAGS_OUTDIR,
    PBI_CREATE_FLAGS_BACKUP,
    PBI_MAKEPATCH_FLAGS_OUTDIR, PBI_MAKEPATCH_FLAGS_NOCHECKSIG,
    PBI_PATCH_FLAGS_OUTDIR, PBI_PATCH_FLAGS_NOCHECKSIG
)
from freenasUI.common.system import (
    exclude_path,
    get_mounted_filesystems,
    umount,
    get_sw_name
)
from freenasUI.common.warden import (Warden, WardenJail,
    WARDEN_TYPE_PLUGINJAIL, WARDEN_STATUS_RUNNING)
from freenasUI.freeadmin.hook import HookMetaclass
from freenasUI.middleware import zfs
from freenasUI.middleware.encryption import random_wipe
from freenasUI.middleware.exceptions import MiddlewareError
from freenasUI.middleware.multipath import Multipath
import sysctl

RE_DSKNAME = re.compile(r'^([a-z]+)([0-9]+)$')
log = logging.getLogger('middleware.notifier')


class StartNotify(threading.Thread):
    """
    Use kqueue to watch for an event before actually calling start/stop
    This should help against synchronization and more responsive notify.
    """

    def __init__(self, pidfile, verb, *args, **kwargs):
        self._pidfile = pidfile
        self._verb = verb
        super(StartNotify, self).__init__(*args, **kwargs)

    def run(self):

        if not self._pidfile:
            return None

        """
        If we are using start or restart we expect that a .pid file will
        exists at the end of the process, so attach to the directory waiting
        for that file.
        Otherwise we will be stopping and expect the .pid to be deleted, so
        attach to the .pid file and wait for it to be removed
        """
        if self._verb in ('start', 'restart'):
            fflags = select.KQ_NOTE_WRITE | select.KQ_NOTE_EXTEND
            _file = os.path.dirname(self._pidfile)
        else:
            fflags = select.KQ_NOTE_WRITE | select.KQ_NOTE_DELETE
            if os.path.exists(self._pidfile):
                _file = self._pidfile
            else:
                _file = os.path.dirname(self._pidfile)
        fd = os.open(_file, os.O_RDONLY)
        evts = [
            select.kevent(fd,
                filter=select.KQ_FILTER_VNODE,
                flags=select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                fflags=fflags,
            )
        ]
        kq = select.kqueue()
        kq.control(evts, 0, 0)

        tries = 1
        while tries < 4:
            kq.control(None, 2, 1)
            if self._verb in ('start', 'restart'):
                if os.path.exists(self._pidfile):
                    # The file might have been created but it may take a little bit
                    # for the daemon to write the PID
                    time.sleep(0.1)
                if os.path.exists(self._pidfile) and os.stat(self._pidfile).st_size > 0:
                    break
            elif self._verb == "stop" and not os.path.exists(self._pidfile):
                break
            tries += 1
        kq.close()
        os.close(fd)


class notifier:

    __metaclass__ = HookMetaclass

    from os import system as __system
    from pwd import getpwnam as ___getpwnam
    from grp import getgrnam as ___getgrnam
    IDENTIFIER = 'notifier'

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
            self.__system("(" + command + ") 2>&1 | logger -p daemon.notice -t %s"
                           % (self.IDENTIFIER, ))
        finally:
            libc.sigprocmask(signal.SIGQUIT, pomask, None)
        log.debug("Executed: %s", command)

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

    def _pipeopen(self, command):
        log.debug("Popen()ing: %s", command)
        return Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True, close_fds=True)

    def _do_nada(self):
        pass

    def _simplecmd(self, action, what):
        log.debug("Calling: %s(%s) ", action, what)
        f = getattr(self, '_' + action + '_' + what, None)
        if f is None:
            # Provide generic start/stop/restart verbs for rc.d scripts
            if action in ("start", "stop", "restart", "reload"):
                if action == 'restart':
                    self._system("/usr/sbin/service " + what + " forcestop ")
                self._system("/usr/sbin/service " + what + " " + action)
                f = self._do_nada
            else:
                raise ValueError("Internal error: Unknown command")
        f()

    __service2daemon = {
            'ssh': ('sshd', '/var/run/sshd.pid'),
            'rsync': ('rsync', '/var/run/rsyncd.pid'),
            'nfs': ('nfsd', None),
            'afp': ('netatalk', None),
            'cifs': ('smbd', '/var/run/samba/smbd.pid'),
            'dynamicdns': ('inadyn-mt', None),
            'snmp': ('bsnmpd', '/var/run/snmpd.pid'),
            'ftp': ('proftpd', '/var/run/proftpd.pid'),
            'tftp': ('inetd', '/var/run/inetd.pid'),
            'iscsitarget': ('istgt', '/var/run/istgt.pid'),
            'ctld': ('ctld', '/var/run/ctld.pid'),
            'lldp': ('ladvd', '/var/run/ladvd.pid'),
            'ups': ('upsd', '/var/db/nut/upsd.pid'),
            'upsmon': ('upsmon', '/var/db/nut/upsmon.pid'),
            'smartd': ('smartd', '/var/run/smartd.pid'),
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
        self._system_nolog("/usr/local/bin/python /usr/local/www/freenasUI/tools/webshell.py")

    def _restart_iscsitarget(self):
        self._system("/usr/sbin/service ix-ctld quietstart")
        self._system("/usr/sbin/service ctld forcestop")
        self._system("/usr/sbin/service ctld restart")

    def _start_iscsitarget(self):
        self._system("/usr/sbin/service ix-ctld quietstart")
        self._system("/usr/sbin/service ctld restart")

    def _stop_iscsitarget(self):
        self._system("/usr/sbin/service ctld forcestop")

    def _reload_iscsitarget(self):
        self._system("/usr/sbin/service ix-ctld quietstart")
        self._system("/usr/sbin/service ctld reload")

    def _start_collectd(self):
        self._system("/usr/sbin/service ix-collectd quietstart")
        self._system("/usr/sbin/service collectd restart")

    def _restart_collectd(self):
        self._system("/usr/sbin/service ix-collectd quietstart")
        self._system("/usr/sbin/service collectd restart")

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

    def _stop_jails(self):
        from freenasUI.jails.models import Jails
        for jail in Jails.objects.all():
            Warden().stop(jail=jail.jail_host)

    def _start_jails(self):
        self._system("/usr/sbin/service ix-warden start")
        from freenasUI.jails.models import Jails
        for jail in Jails.objects.all():
            Warden().start(jail=jail.jail_host)
        self._system("/usr/sbin/service ix-plugins start")
        self.reload("http")

    def _restart_jails(self):
        self._stop_jails()
        self._start_jails()

    def _stop_pbid(self):
        self._system_nolog("/usr/sbin/service pbid stop")

    def _start_pbid(self):
        self._system_nolog("/usr/sbin/service pbid start")

    def _restart_pbid(self):
        self._system_nolog("/usr/sbin/service pbid restart")

    def ifconfig_alias(self, iface, oldip=None, newip=None, oldnetmask=None, newnetmask=None):
        if not iface:
            return False

        cmd = "/sbin/ifconfig %s" % iface
        if newip and newnetmask:
            cmd += " alias %s/%s" % (newip, newnetmask)

        elif newip:
            cmd += " alias %s" % newip

        else:
            cmd = None

        if cmd:
            p = self._pipeopen(cmd)
            if p.wait() != 0:
                return False

        cmd = "/sbin/ifconfig %s" % iface
        if newip:
            cmd += " -alias %s" % oldip
            p = self._pipeopen(cmd)
            if p.wait() != 0:
                return False

        if newnetmask and not newip:
            cmd += " alias %s/%s" % (oldip, newnetmask)

        else:
            cmd = None

        if cmd:
            p = self._pipeopen(cmd)
            if p.wait() != 0:
                return False

        return True

    def _reload_named(self):
        self._system("/usr/sbin/service named reload")

    def _reload_hostname(self):
        self._system('/bin/hostname ""')
        self._system("/usr/sbin/service ix-hostname quietstart")
        self._system("/usr/sbin/service hostname quietstart")

    def _reload_networkgeneral(self):
        self._system('/bin/hostname ""')
        self._system("/usr/sbin/service ix-hostname quietstart")
        self._system("/usr/sbin/service hostname quietstart")
        self._system("/usr/sbin/service routing restart")

    def _reload_timeservices(self):
        self._system("/usr/sbin/service ix-localtime quietstart")
        self._system("/usr/sbin/service ix-ntpd quietstart")
        self._system("/usr/sbin/service ntpd restart")
        c = self.__open_db()
        c.execute("SELECT stg_timezone FROM system_settings ORDER BY -id LIMIT 1")
        os.environ['TZ'] = c.fetchone()[0]
        time.tzset()

    def _restart_smartd(self):
        self._system("/usr/sbin/service ix-smartd quietstart")
        self._system("/usr/sbin/service smartd forcestop")
        self._system("/usr/sbin/service smartd restart")

    def _reload_ssh(self):
        self._system("/usr/sbin/service ix-sshd quietstart")
        self._system("/usr/sbin/service ix_register reload")
        self._system("/usr/sbin/service sshd reload")

    def _start_ssh(self):
        self._system("/usr/sbin/service ix-sshd quietstart")
        self._system("/usr/sbin/service ix_register reload")
        self._system("/usr/sbin/service sshd start")

    def _stop_ssh(self):
        self._system("/usr/sbin/service sshd forcestop")
        self._system("/usr/sbin/service ix_register reload")

    def _restart_ssh(self):
        self._system("/usr/sbin/service ix-sshd quietstart")
        self._system("/usr/sbin/service sshd forcestop")
        self._system("/usr/sbin/service ix_register reload")
        self._system("/usr/sbin/service sshd restart")

    def _reload_rsync(self):
        self._system("/usr/sbin/service ix-rsyncd quietstart")
        self._system("/usr/sbin/service rsyncd restart")

    def _restart_rsync(self):
        self._stop_rsync()
        self._start_rsync()

    def _start_rsync(self):
        self._system("/usr/sbin/service ix-rsyncd quietstart")
        self._system("/usr/sbin/service rsyncd start")

    def _stop_rsync(self):
        self._system("/usr/sbin/service rsyncd forcestop")

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

    def _start_lldp(self):
        self._system("/usr/sbin/service ladvd start")

    def _stop_lldp(self):
        self._system("/usr/sbin/service ladvd forcestop")

    def _restart_lldp(self):
        self._system("/usr/sbin/service ladvd forcestop")
        self._system("/usr/sbin/service ladvd restart")

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

    def _restart_syslogd(self):
        self._system("/usr/sbin/service ix-syslogd quietstart")
        self._system("/usr/sbin/service syslogd restart")

    def _start_syslogd(self):
        self._system("/usr/sbin/service ix-syslogd quietstart")
        self._system("/usr/sbin/service syslogd start")

    def _reload_tftp(self):
        self._system("/usr/sbin/service ix-inetd quietstart")
        self._system("/usr/sbin/service inetd forcestop")
        self._system("/usr/sbin/service inetd restart")

    def _restart_tftp(self):
        self._system("/usr/sbin/service ix-inetd quietstart")
        self._system("/usr/sbin/service inetd forcestop")
        self._system("/usr/sbin/service inetd restart")

    def _restart_cron(self):
        self._system("/usr/sbin/service ix-crontab quietstart")

    def _start_motd(self):
        self._system("/usr/sbin/service ix-motd quietstart")
        self._system("/usr/sbin/service motd quietstart")

    def _start_ttys(self):
        self._system("/usr/sbin/service ix-ttys quietstart")

    def _reload_ftp(self):
        self._system("/usr/sbin/service ix-proftpd quietstart")
        self._system("/usr/sbin/service proftpd restart")

    def _restart_ftp(self):
        self._stop_ftp()
        self._start_ftp()
        self._system("sleep 1")

    def _start_ftp(self):
        self._system("/usr/sbin/service ix-proftpd quietstart")
        self._system("/usr/sbin/service proftpd start")

    def _stop_ftp(self):
        self._system("/usr/sbin/service proftpd forcestop")

    def _start_ups(self):
        self._system("/usr/sbin/service ix-ups quietstart")
        self._system("/usr/sbin/service nut start")
        self._system("/usr/sbin/service nut_upsmon start")
        self._system("/usr/sbin/service nut_upslog start")

    def _stop_ups(self):
        self._system("/usr/sbin/service nut_upslog forcestop")
        self._system("/usr/sbin/service nut_upsmon forcestop")
        self._system("/usr/sbin/service nut forcestop")

    def _restart_ups(self):
        self._system("/usr/sbin/service ix-ups quietstart")
        self._system("/usr/sbin/service nut forcestop")
        self._system("/usr/sbin/service nut_upsmon forcestop")
        self._system("/usr/sbin/service nut_upslog forcestop")
        self._system("/usr/sbin/service nut restart")
        self._system("/usr/sbin/service nut_upsmon restart")
        self._system("/usr/sbin/service nut_upslog restart")

    def _started_ups(self):
        from freenasUI.services.models import UPS
        mode = UPS.objects.order_by('-id')[0].ups_mode
        if mode == "master":
            svc = "ups"
        else:
            svc = "upsmon"
        sn = self._started_notify("start", "upsmon")
        return self._started(svc, sn)

    def _load_afp(self):
        self._system("/usr/sbin/service ix-afpd quietstart")
        self._system("/usr/sbin/service netatalk quietstart")

    def _start_afp(self):
        self._system("/usr/sbin/service ix-afpd start")
        self._system("/usr/sbin/service netatalk start")

    def _stop_afp(self):
        self._system("/usr/sbin/service netatalk forcestop")

    def _restart_afp(self):
        self._stop_afp()
        self._start_afp()

    def _reload_afp(self):
        self._system("/usr/sbin/service ix-afpd quietstart")
        self._system("killall -1 netatalk")

    def _reload_nfs(self):
        self._system("/usr/sbin/service ix-nfsd quietstart")

    def _restart_nfs(self):
        self._stop_nfs()
        self._start_nfs()

    def _stop_nfs(self):
        self._system("/usr/sbin/service rpcbind forcestop")
        self._system("/usr/sbin/service lockd forcestop")
        self._system("/usr/sbin/service statd forcestop")
        self._system("/usr/sbin/service gssd forcetstop")
        self._system("/usr/sbin/service nfsuserd forcestop")
        self._system("/usr/sbin/service mountd forcestop")
        self._system("/usr/sbin/service nfsd forcestop")

    def _start_nfs(self):
        self._system("/usr/sbin/service ix-nfsd quietstart")
        self._system("/usr/sbin/service rpcbind quietstart")
        self._system("/usr/sbin/service gssd quietstart")
        self._system("/usr/sbin/service mountd quietstart")
        self._system("/usr/sbin/service nfsd quietstart")
        self._system("/usr/sbin/service statd quietstart")
        self._system("/usr/sbin/service lockd quietstart")

    def _stop_nfsv4(self):
        self._system("/usr/sbin/service gssd quietstop")
        self._system("/usr/sbin/service nfsuserd quietstop")
        self._system("/usr/sbin/service ix-nfsd quietstart")

    def _start_nfsv4(self):
        self._system("/usr/sbin/service gssd quietstart")
        self._system("/usr/sbin/service ix-nfsd quietstart")

    def _force_stop_jail(self):
        self._system("/usr/sbin/service jail forcestop")

    def _start_plugins(self, jail=None, plugin=None):
        if jail and plugin:
            self._system_nolog("/usr/sbin/service ix-plugins forcestart %s:%s" % (jail, plugin))
        else:
            self._system_nolog("/usr/sbin/service ix-plugins forcestart")

    def _stop_plugins(self, jail=None, plugin=None):
        if jail and plugin:
            self._system_nolog("/usr/sbin/service ix-plugins forcestop %s:%s" % (jail, plugin))
        else:
            self._system_nolog("/usr/sbin/service ix-plugins forcestop")

    def _restart_plugins(self, jail=None, plugin=None):
        self._stop_plugins(jail=jail, plugin=plugin)
        self._start_plugins(jail=jail, plugin=plugin)

    def _started_plugins(self, jail=None, plugin=None):
        res = False
        if jail and plugin:
            if self._system_nolog("/usr/sbin/service ix-plugins status %s:%s" % (jail, plugin)) == 0:
                res = True
        else:
            if self._system_nolog("/usr/sbin/service ix-plugins status") == 0:
                res = True
        return res

    def pluginjail_running(self, pjail=None):
        running = False

        try:
            wlist = Warden().list()
            for wj in wlist:
                wj = WardenJail(**wj)
                if pjail and wj.host == pjail:
                    if wj.type == WARDEN_TYPE_PLUGINJAIL and \
                        wj.status == WARDEN_STATUS_RUNNING:
                        running = True
                        break

                elif not pjail and wj.type == WARDEN_TYPE_PLUGINJAIL and \
                    wj.status == WARDEN_STATUS_RUNNING:
                    running = True
                    break
        except:
            pass

        return running

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

    def _restart_dynamicdns(self):
        self._system("/usr/sbin/service ix-inadyn quietstart")
        self._system("/usr/sbin/service inadyn-mt forcestop")
        self._system("/usr/sbin/service inadyn-mt restart")

    def _restart_system(self):
        self._system("/bin/sleep 3 && /sbin/shutdown -r now &")

    def _stop_system(self):
        self._system("/sbin/shutdown -p now")

    def _reload_cifs(self):
        self._system("/usr/sbin/service ix-samba quietstart")
        self._system("/usr/sbin/service samba_server forcereload")

    def _restart_cifs(self):
        self._system("/usr/sbin/service ix-samba quietstart")
        self._system("/usr/sbin/service samba_server forcestop")
        self._system("/usr/sbin/service samba_server quietrestart")

    def _start_cifs(self):
        self._system("/usr/sbin/service ix-samba quietstart")
        self._system("/usr/sbin/service samba_server quietstart")

    def _stop_cifs(self):
        self._system("/usr/sbin/service samba_server forcestop")

    def _start_snmp(self):
        self._system("/usr/sbin/service ix-bsnmpd quietstart")
        self._system("/usr/sbin/service bsnmpd quietstart")

    def _stop_snmp(self):
        self._system("/usr/sbin/service bsnmpd quietstop")

    def _restart_snmp(self):
        self._system("/usr/sbin/service ix-bsnmpd quietstart")
        self._system("/usr/sbin/service bsnmpd forcestop")
        self._system("/usr/sbin/service bsnmpd quietstart")

    def _restart_http(self):
        self._system("/usr/sbin/service ix-nginx quietstart")
        self._system("/usr/sbin/service ix_register reload")
        self._system("/usr/sbin/service nginx restart")

    def _reload_http(self):
        self._system("/usr/sbin/service ix-nginx quietstart")
        self._system("/usr/sbin/service ix_register reload")
        self._system("/usr/sbin/service nginx reload")

    def _reload_loader(self):
        self._system("/usr/sbin/service ix-loader reload")

    def _start_loader(self):
        self._system("/usr/sbin/service ix-loader quietstart")

    def __saver_loaded(self):
        pipe = os.popen("kldstat|grep daemon_saver")
        out = pipe.read().strip('\n')
        pipe.close()
        return (len(out) > 0)

    def _start_saver(self):
        if not self.__saver_loaded():
            self._system("kldload daemon_saver")

    def _stop_saver(self):
        if self.__saver_loaded():
            self._system("kldunload daemon_saver")

    def _restart_saver(self):
        self._stop_saver()
        self._start_saver()

    def __open_db(self, ret_conn=False):
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

    def __gpt_labeldisk(self, type, devname, swapsize=2):
        """Label the whole disk with GPT under the desired label and type"""

        # Calculate swap size.
        swapgb = swapsize
        swapsize = swapsize * 1024 * 1024 * 2
        # Round up to nearest whole integral multiple of 128 and subtract by 34
        # so next partition starts at mutiple of 128.
        swapsize = ((swapsize+127)/128)*128
        # To be safe, wipe out the disk, both ends... before we start
        self._system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (devname, ))
        try:
            p1 = self._pipeopen("diskinfo %s" % (devname, ))
            size = int(re.sub(r'\s+', ' ', p1.communicate()[0]).split()[2]) / (1024)
        except:
            log.error("Unable to determine size of %s", devname)
        else:
            # The GPT header takes about 34KB + alignment, round it to 100
            if size - 100 <= swapgb * 1024 * 1024:
                raise MiddlewareError('Your disk size must be higher than %dGB' % (swapgb, ))
            # HACK: force the wipe at the end of the disk to always succeed. This
            # is a lame workaround.
            self._system("dd if=/dev/zero of=/dev/%s bs=1m oseek=%s" % (
                devname,
                size / 1024 - 4,
                ))

        commands = []
        commands.append("gpart create -s gpt /dev/%s" % (devname, ))
        if swapsize > 0:
            commands.append("gpart add -a 4k -b 128 -t freebsd-swap -s %d %s" % (swapsize, devname))
            commands.append("gpart add -a 4k -t %s %s" % (type, devname))
        else:
            commands.append("gpart add -a 4k -b 128 -t %s %s" % (type, devname))

        # Install a dummy boot block so system gives meaningful message if booting
        # from the wrong disk.
        commands.append("gpart bootcode -b /boot/pmbr-datadisk /dev/%s" % (devname))

        for command in commands:
            proc = self._pipeopen(command)
            proc.wait()
            if proc.returncode != 0:
                raise MiddlewareError('Unable to GPT format the disk "%s"' % devname)

        # We might need to sync with reality (e.g. devname -> uuid)
        # Invalidating confxml is required or changes wont be seen
        self.__confxml = None
        self.sync_disk(devname)

    def __gpt_unlabeldisk(self, devname):
        """Unlabel the disk"""
        swapdev = self.part_type_from_device('swap', devname)
        if swapdev != '':
            self._system("swapoff /dev/%s.eli" % swapdev)
            self._system("geli detach /dev/%s" % swapdev)
        self._system("gpart destroy -F /dev/%s" % devname)

        # Wipe out the partition table by doing an additional iterate of create/destroy
        self._system("gpart create -s gpt /dev/%s" % devname)
        self._system("gpart destroy -F /dev/%s" % devname)

        # We might need to sync with reality (e.g. uuid -> devname)
        # Invalidating confxml is required or changes wont be seen
        self.__confxml = None
        self.sync_disk(devname)

    def unlabel_disk(self, devname):
        # TODO: Check for existing GPT or MBR, swap, before blindly call __gpt_unlabeldisk
        self.__gpt_unlabeldisk(devname)

    def __encrypt_device(self, devname, diskname, volume, passphrase=None):
        from freenasUI.storage.models import Disk, EncryptedDisk

        geli_keyfile = volume.get_geli_keyfile()
        if not os.path.exists(geli_keyfile):
            if not os.path.exists(GELI_KEYPATH):
                self._system("mkdir -p %s" % (GELI_KEYPATH, ))
            self._system("dd if=/dev/random of=%s bs=64 count=1" % (geli_keyfile, ))

        if passphrase is not None:
            _passphrase = " -J %s" % passphrase
            _passphrase2 = "-j %s" % passphrase
        else:
            _passphrase = "-P"
            _passphrase2 = "-p"

        self._system("geli init -s 4096 -B none %s -K %s /dev/%s" % (_passphrase, geli_keyfile, devname))
        self._system("geli attach %s -k %s /dev/%s" % (_passphrase2, geli_keyfile, devname))
        # TODO: initialize the provider in background (wipe with random data)

        if diskname.startswith('multipath/'):
            diskobj = Disk.objects.get(
                disk_multipath_name=diskname.replace('multipath/', '')
            )
        else:
            ident = self.device_to_identifier(diskname)
            diskobj = Disk.objects.get(disk_identifier=ident)
        encdiskobj = EncryptedDisk()
        encdiskobj.encrypted_volume = volume
        encdiskobj.encrypted_disk = diskobj
        encdiskobj.encrypted_provider = devname
        encdiskobj.save()

        return ("/dev/%s.eli" % devname)

    def geli_setkey(self, dev, key, passphrase=None, slot=0):
        command = ["geli", "setkey", "-n", str(slot)]
        if passphrase:
            command.extend(["-J", passphrase])
        else:
            command.append("-P")
        command.extend(["-K", key, dev])
        proc = self._pipeopen(' '.join(command))
        err = proc.communicate()[1]
        if proc.returncode != 0:
            raise MiddlewareError("Unable to set passphrase: %s" % (err, ))

    def geli_passphrase(self, volume, passphrase, rmrecovery=False):
        """
        Set a passphrase in a geli
        If passphrase is None then remove the passphrase

        Raises:
            MiddlewareError
        """
        geli_keyfile = volume.get_geli_keyfile()
        if passphrase:
            _passphrase = "-J %s" % (passphrase, )
        else:
            _passphrase = "-P"
        for ed in volume.encrypteddisk_set.all():
            dev = ed.encrypted_provider
            """
            A new passphrase cannot be set without destroying the recovery key
            """
            if rmrecovery is True:
                proc = self._pipeopen("geli delkey -n 1 %s" % (dev, ))
                proc.communicate()
            proc = self._pipeopen("geli setkey -n 0 %s -K %s %s" % (
                _passphrase,
                geli_keyfile,
                dev,
                )
            )
            err = proc.communicate()[1]
            if proc.returncode != 0:
                raise MiddlewareError("Unable to set passphrase: %s" % (err, ))

    def geli_rekey(self, volume, slot=0):
        """
        Regenerates the geli global key and set it to devs
        Removes the passphrase if it was present

        Raises:
            MiddlewareError
        """

        geli_keyfile = volume.get_geli_keyfile()

        # Generate new key as .tmp
        self._system("dd if=/dev/random of=%s.tmp bs=64 count=1" % (geli_keyfile, ))
        error = False
        applied = []
        for ed in volume.encrypteddisk_set.all():
            dev = ed.encrypted_provider
            proc = self._pipeopen("geli setkey -P -n %d -K %s.tmp %s" % (
                slot,
                geli_keyfile,
                dev,
                )
            )
            err = proc.communicate()[1]
            if proc.returncode != 0:
                error = True
                break
            applied.append(dev)

        # Try to be atomic in a certain way
        # If rekey failed for one of the devs, revert for the ones already applied
        if error:
            for dev in applied:
                proc = self._pipeopen("geli setkey -P -n %d -k %s.tmp -K %s %s" % (
                    slot,
                    geli_keyfile,
                    geli_keyfile,
                    dev,
                    )
                )
                proc.communicate()
            raise MiddlewareError("Unable to set key: %s" % (err, ))
        else:
            self._system("mv %s.tmp %s" % (geli_keyfile, geli_keyfile))
            if volume.vol_encrypt != 1:
                volume.vol_encrypt = 1
                volume.save()

    def geli_recoverykey_add(self, volume, passphrase=None):

        reckey_file = tempfile.mktemp(dir='/tmp/')
        self._system("dd if=/dev/random of=%s bs=64 count=1" % (reckey_file, ))

        for ed in volume.encrypteddisk_set.all():
            dev = ed.encrypted_provider
            if passphrase is not None:
                proc = self._pipeopen("geli setkey -n 1 -K %s -J %s %s" % (
                    reckey_file,
                    passphrase,
                    dev,
                    )
                    )
            else:
                proc = self._pipeopen("geli setkey -n 1 -K %s -P %s" % (
                    reckey_file,
                    dev,
                    )
                    )
            err = proc.communicate()[1]
            if proc.returncode != 0:
                raise MiddlewareError("Unable to set recovery key: %s" % (err, ))
        return reckey_file

    def geli_delkey(self, volume, slot=1):

        for ed in volume.encrypteddisk_set.all():
            dev = ed.encrypted_provider
            proc = self._pipeopen("geli delkey -n %d %s" % (
                slot,
                dev,
                ))

            err = proc.communicate()[1]
            if proc.returncode != 0:
                raise MiddlewareError("Unable to remove key: %s" % (err, ))

    def geli_is_decrypted(self, dev):
        doc = self._geom_confxml()
        geom = doc.xpath("//class[name = 'ELI']/geom[name = '%s.eli']" % (
            dev,
        ))
        if geom:
            return True
        return False

    def geli_attach_single(self, prov, key, passphrase=None):
        if not passphrase:
            _passphrase = "-p"
        else:
            _passphrase = "-j %s" % passphrase
        proc = self._pipeopen("geli attach %s -k %s %s" % (
            _passphrase,
            key,
            prov,
            ))
        proc.communicate()
        if os.path.exists("/dev/%s.eli" % prov):
            return True
        return False

    def geli_attach(self, volume, passphrase=None, key=None):
        """
        Attach geli providers of a given volume

        Returns the number of providers that failed to attach
        """
        failed = 0
        if key is None:
            geli_keyfile = volume.get_geli_keyfile()
        else:
            geli_keyfile = key
        if not passphrase:
            _passphrase = "-p"
        else:
            _passphrase = "-j %s" % passphrase
        for ed in volume.encrypteddisk_set.all():
            dev = ed.encrypted_provider
            proc = self._pipeopen("geli attach %s -k %s %s" % (
                _passphrase,
                geli_keyfile,
                dev,
            ))
            err = proc.communicate()[1]
            if proc.returncode != 0:
                log.warn("Failed to geli attach %s: %s", dev, err)
                failed += 1
        return failed

    def geli_testkey(self, volume, passphrase=None):
        """
        Test key for geli providers of a given volume
        """

        assert volume.vol_fstype == 'ZFS'

        geli_keyfile = volume.get_geli_keyfile()
        if not passphrase:
            _passphrase = "-p"
        else:
            _passphrase = "-j %s" % passphrase

        """
        Parse zpool status to get encrypted providers
        EncryptedDisk table might be out of sync for some reason,
        this is much more reliable!
        """
        zpool = self.zpool_parse(volume.vol_name)
        for dev in zpool.get_devs():
            if not dev.name.endswith(".eli"):
                continue
            proc = self._pipeopen("geli attach %s -k %s %s" % (
               _passphrase,
               geli_keyfile,
               dev.name.replace(".eli", ""),
               ))
            err = proc.communicate()[1]
            if err.find('Wrong key') != -1:
                return False
        return True

    def geli_detach(self, dev):
        """
        Detach geli provider

        Returns false if a device suffixed with .eli exists at the end of
        the operation and true otherwise
        """
        proc = self._pipeopen("geli detach %s" % (
            dev,
            ))
        err = proc.communicate()[1]
        if proc.returncode != 0:
            log.warn("Failed to geli detach %s: %s", dev, err)
        if os.path.exists("/dev/%s.eli"):
            return False
        return True

    def geli_get_all_providers(self):
        """
        Get all unused geli providers

        It might be an entire disk or a partition of type freebsd-zfs
        (GELI on UFS not supported yet)
        """
        providers = []
        doc = self._geom_confxml()
        disks = self.get_disks()
        for disk in disks:
            parts = [node.text for node in doc.xpath("//class[name = 'PART']/geom[name = '%s']/provider/config[type = 'freebsd-zfs']/../name" % disk)]
            if not parts:
                parts = [disk]
            for part in parts:
                proc = self._pipeopen("geli dump %s" % part)
                proc.communicate()
                if proc.returncode == 0:
                    gptid = doc.xpath("//class[name = 'LABEL']/geom[name = '%s']/provider/name" % part)
                    if gptid:
                        providers.append((gptid[0].text, part))
                    else:
                        providers.append((part, part))
        return providers

    def __prepare_zfs_vdev(self, disks, swapsize, encrypt, volume):
        vdevs = []
        for disk in disks:
            self.__gpt_labeldisk(type="freebsd-zfs",
                                 devname=disk,
                                 swapsize=swapsize)

        doc = self._geom_confxml()
        for disk in disks:
            devname = self.part_type_from_device('zfs', disk)
            if encrypt:
                uuid = doc.xpath(
                    "//class[name = 'PART']"
                    "/geom//provider[name = '%s']/config/rawuuid" % (devname, )
                )
                if not uuid:
                    log.warn("Could not determine GPT uuid for %s", devname)
                    raise MiddlewareError('Unable to determine GPT UUID for %s' % devname)
                else:
                    devname = self.__encrypt_device("gptid/%s" % uuid[0].text, disk, volume)
            else:
                uuid = doc.xpath(
                    "//class[name = 'PART']"
                    "/geom//provider[name = '%s']/config/rawuuid" % (devname, )
                )
                if not uuid:
                    log.warn("Could not determine GPT uuid for %s", devname)
                    devname = "/dev/%s" % devname
                else:
                    devname = "/dev/gptid/%s" % uuid[0].text
            vdevs.append(devname)

        return vdevs

    def __create_zfs_volume(self, volume, swapsize, groups, path=None, init_rand=False):
        """Internal procedure to create a ZFS volume identified by volume id"""
        z_name = str(volume.vol_name)
        z_vdev = ""
        encrypt = (volume.vol_encrypt >= 1)
        # Grab all disk groups' id matching the volume ID
        self._system("swapoff -a")
        device_list = []

        """
        stripe vdevs must come first because of the ordering in the
        zpool create command.

        e.g. zpool create tank ada0 mirror ada1 ada2
             vs
             zpool create tank mirror ada1 ada2 ada0

        For further details see #2388
        """
        def stripe_first(a, b):
            if a['type'] == 'stripe':
                return -1
            if b['type'] == 'stripe':
                return 1
            return 0

        for vgrp in sorted(groups.values(), cmp=stripe_first):
            vgrp_type = vgrp['type']
            if vgrp_type != 'stripe':
                z_vdev += " " + vgrp_type
            if vgrp_type in ('cache', 'log'):
                vdev_swapsize = 0
            else:
                vdev_swapsize = swapsize
            # Prepare disks nominated in this group
            vdevs = self.__prepare_zfs_vdev(vgrp['disks'], vdev_swapsize, encrypt, volume)
            z_vdev += " ".join([''] + vdevs)
            device_list += vdevs

        # Initialize devices with random data
        if init_rand:
            random_wipe(device_list)

        # Finally, create the zpool.
        # TODO: disallowing cachefile may cause problem if there is
        # preexisting zpool having the exact same name.
        if not os.path.isdir("/data/zfs"):
            os.makedirs("/data/zfs")

        altroot = 'none' if path else '/mnt'
        mountpoint = path if path else ('/%s' % (z_name, ))

        larger_ashift = 0
        try:
            larger_ashift = int(self.sysctl("vfs.zfs.vdev.larger_ashift_minimal"))
        except AssertionError:
            pass
        if larger_ashift == 0:
            self._system("/sbin/sysctl vfs.zfs.vdev.larger_ashift_minimal=1")

        p1 = self._pipeopen("zpool create -o cachefile=/data/zfs/zpool.cache "
                      "-o failmode=continue "
                      "-o autoexpand=on "
                      "-O compression=lz4 "
                      "-O aclmode=passthrough -O aclinherit=passthrough "
                      "-f -m %s -o altroot=%s %s %s" % (mountpoint, altroot, z_name, z_vdev))
        if p1.wait() != 0:
            error = ", ".join(p1.communicate()[1].split('\n'))
            raise MiddlewareError('Unable to create the pool: %s' % error)

        # Restore previous larger ashift state.
        if larger_ashift == 0:
            self._system("/sbin/sysctl vfs.zfs.vdev.larger_ashift_minimal=0")

        # We've our pool, lets retrieve the GUID
        p1 = self._pipeopen("zpool get guid %s" % z_name)
        if p1.wait() == 0:
            line = p1.communicate()[0].split('\n')[1].strip()
            volume.vol_guid = re.sub('\s+', ' ', line).split(' ')[2]
            volume.save()
        else:
            log.warn("The guid of the pool %s could not be retrieved", z_name)

        self.zfs_inherit_option(z_name, 'mountpoint')

        self._system("zpool set cachefile=/data/zfs/zpool.cache %s" % (z_name))
        # TODO: geli detach -l

    def get_swapsize(self):
        from freenasUI.system.models import Advanced
        swapsize = Advanced.objects.latest('id').adv_swapondrive
        return swapsize

    def zfs_volume_attach_group(self, volume, group, encrypt=False):
        """Attach a disk group to a zfs volume"""

        vgrp_type = group['type']
        if vgrp_type in ('log', 'cache'):
            swapsize = 0
        else:
            swapsize = self.get_swapsize()

        assert volume.vol_fstype == 'ZFS'
        z_name = volume.vol_name
        z_vdev = ""
        encrypt = (volume.vol_encrypt >= 1)

        # FIXME swapoff -a is overkill
        self._system("swapoff -a")
        if vgrp_type != 'stripe':
            z_vdev += " " + vgrp_type

        # Prepare disks nominated in this group
        vdevs = self.__prepare_zfs_vdev(group['disks'], swapsize, encrypt, volume)
        z_vdev += " ".join([''] + vdevs)

        larger_ashift = 0
        try:
            larger_ashift = int(self.sysctl("vfs.zfs.vdev.larger_ashift_minimal"))
        except AssertionError:
            pass
        if larger_ashift == 0:
            self._system("/sbin/sysctl vfs.zfs.vdev.larger_ashift_minimal=1")

        # Finally, attach new groups to the zpool.
        self._system("zpool add -f %s %s" % (z_name, z_vdev))

        # Restore previous larger ashift state.
        if larger_ashift == 0:
            self._system("/sbin/sysctl vfs.zfs.vdev.larger_ashift_minimal=0")

        # TODO: geli detach -l
        self._reload_disk()

    def create_zfs_vol(self, name, size, props=None, sparse=False):
        """Internal procedure to create ZFS volume"""
        if sparse is True:
            options = "-s "
        else:
            options = " "
        if props:
            assert isinstance(props, types.DictType)
            for k in props.keys():
                if props[k] != 'inherit':
                    options += "-o %s=%s " % (k, props[k])
        zfsproc = self._pipeopen("/sbin/zfs create %s -V '%s' '%s'" % (options, size, name))
        zfs_err = zfsproc.communicate()[1]
        zfs_error = zfsproc.wait()
        return zfs_error, zfs_err

    def create_zfs_dataset(self, path, props=None, _restart_collectd=True):
        """Internal procedure to create ZFS volume"""
        options = " "
        if props:
            assert isinstance(props, types.DictType)
            for k in props.keys():
                if props[k] != 'inherit':
                    options += "-o %s=%s " % (k, props[k])
        zfsproc = self._pipeopen("/sbin/zfs create %s '%s'" % (options, path))
        zfs_output, zfs_err = zfsproc.communicate()
        zfs_error = zfsproc.wait()
        if zfs_error == 0 and _restart_collectd:
            self.restart("collectd")
        return zfs_error, zfs_err

    def list_zfs_vols(self, volname):
        """Return a dictionary that contains all ZFS volumes list"""
        zfsproc = self._pipeopen("/sbin/zfs list -p -H -o name,volsize,used,avail,refer,compression,compressratio -t volume -r '%s'" % (str(volname),))
        zfs_output, zfs_err = zfsproc.communicate()
        zfs_output = zfs_output.split('\n')
        retval = {}
        for line in zfs_output:
            if line == "":
                continue
            data = line.split('\t')
            retval[data[0]] = {
                'volsize': int(data[1]),
                'used': int(data[2]),
                'avail': int(data[3]),
                'refer': int(data[4]),
                'compression': data[5],
                'compressratio': data[6],
            }
        return retval

    def list_zfs_fsvols(self):
        proc = self._pipeopen("/sbin/zfs list -H -o name -t volume,filesystem")
        out, err = proc.communicate()
        out = out.split('\n')
        retval = OrderedDict()
        if proc.returncode == 0:
            for line in out:
                if not line:
                    continue
                retval[line] = line
        return retval

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

    def destroy_zfs_dataset(self, path, recursive=False):
        retval = None
        if '@' in path:
            try:
                with mntlock(blocking=False):
                    if self.__snapshot_hold(path):
                        retval = 'Held by replication system.'
            except IOError:
                retval = 'Try again later.'
        elif recursive:
            try:
                with mntlock(blocking=False):
                    zfsproc = self._pipeopen("/sbin/zfs list -Hr -t snapshot -o name '%s'" % (path))
                    snaps = zfsproc.communicate()[0]
                    for snap in filter(None, snaps.splitlines()):
                        if self.__snapshot_hold(snap):
                            retval = '%s: Held by replication system.' % snap
                            break
            except IOError:
                retval = 'Try again later.'
        if retval is None:
            mp = self.__get_mountpath(path, 'ZFS')
            if self.contains_jail_root(mp):
                self.delete_plugins()

            if recursive:
                zfsproc = self._pipeopen("zfs destroy -r '%s'" % (path))
            else:
                zfsproc = self._pipeopen("zfs destroy '%s'" % (path))
            retval = zfsproc.communicate()[1]
            if zfsproc.returncode == 0:
                from freenasUI.storage.models import Task, Replication
                Task.objects.filter(task_filesystem=path).delete()
                Replication.objects.filter(repl_filesystem=path).delete()
        if not retval:
            try:
                self.__rmdir_mountpoint(path)
            except MiddlewareError as me:
                retval = str(me)

        return retval

    def destroy_zfs_vol(self, name):
        mp = self.__get_mountpath(name, 'ZFS')
        if self.contains_jail_root(mp):
            self.delete_plugins()
        zfsproc = self._pipeopen("zfs destroy '%s'" % (str(name),))
        retval = zfsproc.communicate()[1]
        return retval

    def __destroy_zfs_volume(self, volume):
        """Internal procedure to destroy a ZFS volume identified by volume id"""
        vol_name = str(volume.vol_name)
        mp = self.__get_mountpath(vol_name, 'ZFS')
        if self.contains_jail_root(mp):
            self.delete_plugins()
        # First, destroy the zpool.
        disks = volume.get_disks()
        self._system("zpool destroy -f %s" % (vol_name, ))

        # Clear out disks associated with the volume
        for disk in disks:
            self.__gpt_unlabeldisk(devname=disk)

    def __create_ufs_volume(self, volume, swapsize, group):
        geom_vdev = ""
        u_name = str(volume.vol_name)
        # TODO: We do not support multiple GEOM levels for now.
        geom_type = group['type']

        if geom_type == '':
            # Grab disk from the group
            disk = group['disks'][0]
            self.__gpt_labeldisk(type="freebsd-ufs", devname=disk, swapsize=swapsize)
            devname = self.part_type_from_device('ufs', disk)
            # TODO: Need to investigate why /dev/gpt/foo can't have label /dev/ufs/bar
            # generated automatically
            p1 = self._pipeopen("newfs -U -L %s /dev/%s" % (u_name, devname))
            stderr = p1.communicate()[1]
            if p1.returncode != 0:
                error = ", ".join(stderr.split('\n'))
                raise MiddlewareError('Volume creation failed: "%s"' % error)
        else:
            # Grab all disks from the group
            for disk in group['disks']:
                # FIXME: turn into a function
                self._system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (disk,))
                self._system("dd if=/dev/zero of=/dev/%s bs=1m oseek=`diskinfo %s "
                      "| awk '{print int($3 / (1024*1024)) - 4;}'`" % (disk, disk))
                geom_vdev += " /dev/" + disk
                # TODO gpt label disks
            self._system("geom %s load" % (geom_type))
            p1 = self._pipeopen("geom %s label %s %s" % (geom_type, volume.vol_name, geom_vdev))
            stdout, stderr = p1.communicate()
            if p1.returncode != 0:
                error = ", ".join(stderr.split('\n'))
                raise MiddlewareError('Volume creation failed: "%s"' % error)
            ufs_device = "/dev/%s/%s" % (geom_type, volume.vol_name)
            self._system("newfs -U -L %s %s" % (u_name, ufs_device))

    def __destroy_ufs_volume(self, volume):
        """Internal procedure to destroy a UFS volume identified by volume id"""
        u_name = str(volume.vol_name)
        mp = self.__get_mountpath(u_name, 'UFS')
        if self.contains_jail_root(mp):
            self.delete_plugins()

        disks = volume.get_disks()
        provider = self.get_label_consumer('ufs', u_name)
        if provider is None:
            return None
        geom_type = provider.xpath("../../name")[0].text.lower()

        if geom_type not in ('mirror', 'stripe', 'raid3'):
            # Grab disk from the group
            disk = disks[0]
            self._system("umount -f /dev/ufs/" + u_name)
            self.__gpt_unlabeldisk(devname=disk)
        else:
            g_name = provider.xpath("../name")[0].text
            self._system("swapoff -a")
            self._system("umount -f /dev/ufs/" + u_name)
            self._system("geom %s stop %s" % (geom_type, g_name))
            # Grab all disks from the group
            for disk in disks:
                self._system("geom %s clear %s" % (geom_type, disk))
                self._system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (disk,))
                self._system("dd if=/dev/zero of=/dev/%s bs=1m oseek=`diskinfo %s "
                      "| awk '{print int($3 / (1024*1024)) - 4;}'`" % (disk, disk))

    def _init_volume(self, volume, *args, **kwargs):
        """Initialize a volume designated by volume_id"""
        swapsize = self.get_swapsize()

        assert volume.vol_fstype == 'ZFS' or volume.vol_fstype == 'UFS'
        if volume.vol_fstype == 'ZFS':
            self.__create_zfs_volume(volume, swapsize, kwargs.pop('groups', False), kwargs.pop('path', None), init_rand=kwargs.pop('init_rand', False))
        elif volume.vol_fstype == 'UFS':
            self.__create_ufs_volume(volume, swapsize, kwargs.pop('groups')['root'])

    def zfs_replace_disk(self, volume, from_label, to_disk, passphrase=None):
        """Replace disk in zfs called `from_label` to `to_disk`"""
        from freenasUI.storage.models import Disk, EncryptedDisk
        swapsize = self.get_swapsize()

        assert volume.vol_fstype == 'ZFS'

        # TODO: Test on real hardware to see if ashift would persist across replace
        from_disk = self.label_to_disk(from_label)
        from_swap = self.part_type_from_device('swap', from_disk)
        encrypt = (volume.vol_encrypt >= 1)

        if from_swap != '':
            self._system('/sbin/swapoff /dev/%s.eli' % (from_swap, ))
            self._system('/sbin/geli detach /dev/%s' % (from_swap, ))

        # to_disk _might_ have swap on, offline it before gpt label
        to_swap = self.part_type_from_device('swap', to_disk)
        if to_swap != '':
            self._system('/sbin/swapoff /dev/%s.eli' % (to_swap, ))
            self._system('/sbin/geli detach /dev/%s' % (to_swap, ))

        # Replace in-place
        if from_disk == to_disk:
            self._system('/sbin/zpool offline %s %s' % (volume.vol_name, from_label))

        self.__gpt_labeldisk(type="freebsd-zfs", devname=to_disk, swapsize=swapsize)

        # There might be a swap after __gpt_labeldisk
        to_swap = self.part_type_from_device('swap', to_disk)
        # It has to be a freebsd-zfs partition there
        to_label = self.part_type_from_device('zfs', to_disk)

        if to_label == '':
            raise MiddlewareError('freebsd-zfs partition could not be found')

        doc = self._geom_confxml()
        uuid = doc.xpath(
            "//class[name = 'PART']"
            "/geom//provider[name = '%s']/config/rawuuid" % (to_label, )
        )
        if not encrypt:
            if not uuid:
                log.warn("Could not determine GPT uuid for %s", to_label)
                devname = to_label
            else:
                devname = "gptid/%s" % uuid[0].text
        else:
            if not uuid:
                log.warn("Could not determine GPT uuid for %s", to_label)
                raise MiddlewareError('Unable to determine GPT UUID for %s' % devname)
            else:
                from_diskobj = Disk.objects.filter(disk_name=from_disk, disk_enabled=True)
                if from_diskobj.exists():
                    EncryptedDisk.objects.filter(encrypted_volume=volume, encrypted_disk=from_diskobj[0]).delete()
                devname = self.__encrypt_device("gptid/%s" % uuid[0].text, to_disk, volume, passphrase=passphrase)

        larger_ashift = 0
        try:
            larger_ashift = int(self.sysctl("vfs.zfs.vdev.larger_ashift_minimal"))
        except AssertionError:
            pass
        if larger_ashift == 1:
            self._system("/sbin/sysctl vfs.zfs.vdev.larger_ashift_minimal=0")

        if from_disk == to_disk:
            self._system('/sbin/zpool online %s %s' % (volume.vol_name, to_label))
            ret = self._system_nolog('/sbin/zpool replace %s %s' % (volume.vol_name, to_label))
            if ret == 256:
                ret = self._system_nolog('/sbin/zpool scrub %s' % (volume.vol_name))
        else:
            p1 = self._pipeopen('/sbin/zpool replace %s %s %s' % (volume.vol_name, from_label, devname))
            stdout, stderr = p1.communicate()
            ret = p1.returncode
            if ret != 0:
                if from_swap != '':
                    self._system('/sbin/geli onetime /dev/%s' % (from_swap))
                    self._system('/sbin/swapon /dev/%s.eli' % (from_swap))
                error = ", ".join(stderr.split('\n'))
                if to_swap != '':
                    self._system('/sbin/swapoff /dev/%s.eli' % (to_swap, ))
                    self._system('/sbin/geli detach /dev/%s' % (to_swap, ))
                if encrypt:
                    self._system('/sbin/geli detach %s' % (devname, ))
                raise MiddlewareError('Disk replacement failed: "%s"' % error)
            # TODO: geli detach -l

        # Restore previous larger ashift state.
        if larger_ashift == 1:
            self._system("/sbin/sysctl vfs.zfs.vdev.larger_ashift_minimal=1")

        if to_swap:
            self._system('/sbin/geli onetime /dev/%s' % (to_swap))
            self._system('/sbin/swapon /dev/%s.eli' % (to_swap))

        return ret

    def zfs_offline_disk(self, volume, label):
        from freenasUI.storage.models import EncryptedDisk

        assert volume.vol_fstype == 'ZFS'

        # TODO: Test on real hardware to see if ashift would persist across replace
        disk = self.label_to_disk(label)
        swap = self.part_type_from_device('swap', disk)

        if swap != '':
            self._system('/sbin/swapoff /dev/%s.eli' % (swap, ))
            self._system('/sbin/geli detach /dev/%s' % (swap, ))

        # Replace in-place
        p1 = self._pipeopen('/sbin/zpool offline %s %s' % (volume.vol_name, label))
        stderr = p1.communicate()[1]
        if p1.returncode != 0:
            error = ", ".join(stderr.split('\n'))
            raise MiddlewareError('Disk offline failed: "%s"' % error)
        if label.endswith(".eli"):
            self._system("/sbin/geli detach /dev/%s" % label)
            EncryptedDisk.objects.filter(
                encrypted_volume=volume,
                encrypted_provider=label[:-4]
            ).delete()

    def zfs_detach_disk(self, volume, label):
        """Detach a disk from zpool
           (more technically speaking, a replaced disk.  The replacement actually
           creates a mirror for the device to be replaced)"""

        assert volume.vol_fstype == 'ZFS'

        from_disk = self.label_to_disk(label)
        if not from_disk:
            if not re.search(r'^[0-9]+$', label):
                log.warn("Could not find disk for the ZFS label %s", label)
        else:
            from_swap = self.part_type_from_device('swap', from_disk)

            # Remove the swap partition for another time to be sure.
            # TODO: swap partition should be trashed instead.
            if from_swap != '':
                self._system('/sbin/swapoff /dev/%s.eli' % (from_swap,))
                self._system('/sbin/geli detach /dev/%s' % (from_swap,))

        ret = self._system_nolog('/sbin/zpool detach %s %s' % (volume.vol_name, label))
        if from_disk:
            # TODO: This operation will cause damage to disk data which should be limited
            self.__gpt_unlabeldisk(from_disk)
        return ret

    def zfs_remove_disk(self, volume, label):
        """
        Remove a disk from zpool
        Cache disks, inactive hot-spares (and log devices in zfs 28) can be removed
        """

        assert volume.vol_fstype == 'ZFS'

        from_disk = self.label_to_disk(label)
        from_swap = self.part_type_from_device('swap', from_disk)

        if from_swap != '':
            self._system('/sbin/swapoff /dev/%s.eli' % (from_swap,))
            self._system('/sbin/geli detach /dev/%s' % (from_swap,))

        p1 = self._pipeopen('/sbin/zpool remove %s %s' % (volume.vol_name, label))
        stderr = p1.communicate()[1]
        if p1.returncode != 0:
            error = ", ".join(stderr.split('\n'))
            raise MiddlewareError('Disk could not be removed: "%s"' % error)
        # TODO: This operation will cause damage to disk data which should be limited

        if from_disk:
            self.__gpt_unlabeldisk(from_disk)

    def detach_volume_swaps(self, volume):
        """Detach all swaps associated with volume"""
        disks = volume.get_disks()
        for disk in disks:
            swapdev = self.part_type_from_device('swap', disk)
            if swapdev != '':
                self._system("swapoff /dev/%s.eli" % swapdev)
                self._system("geli detach /dev/%s" % swapdev)

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

    def _destroy_volume(self, volume):
        """Destroy a volume on the system

        This either destroys a zpool or umounts a generic volume (e.g. NTFS,
        UFS, etc) and nukes it.

        In the event that the volume is still in use in the OS, the end-result
        is implementation defined depending on the filesystem, and the set of
        commands used to export the filesystem.

        Finally, this method goes and cleans up the mountpoint, as it's
        assumed to be no longer needed. This is also a sanity check to ensure
        that cleaning up everything worked.

        XXX: doing recursive unmounting here might be a good idea.
        XXX: better feedback about files in use might be a good idea...
             someday. But probably before getting to this point. This is a
             tricky problem to fix in a way that doesn't unnecessarily suck up
             resources, but also ensures that the user is provided with
             meaningful data.
        XXX: divorce this from storage.models; depending on storage.models
             introduces a circular dependency and creates design ugliness.
        XXX: implement destruction algorithm for non-UFS/-ZFS.

        Parameters:
            volume: a storage.models.Volume object.

        Raises:
            MiddlewareError: the volume could not be detached cleanly.
            MiddlewareError: the volume's mountpoint couldn't be removed.
            ValueError: 'destroy' isn't implemented for the said filesystem.
        """

        # volume_detach compatibility.
        vol_name, vol_fstype = volume.vol_name, volume.vol_fstype

        vol_mountpath = self.__get_mountpath(vol_name, vol_fstype)

        if vol_fstype == 'ZFS':
            self.__destroy_zfs_volume(volume)
        elif vol_fstype == 'UFS':
            self.__destroy_ufs_volume(volume)
        else:
            raise ValueError("destroy isn't implemented for the %s filesystem"
                             % (vol_fstype, ))

        self._reload_disk()
        self._encvolume_detach(volume)
        self.__rmdir_mountpoint(vol_mountpath)

    def _reload_disk(self):
        self._system("/usr/sbin/service ix-fstab quietstart")
        self._system("/usr/sbin/service encswap quietstart")
        self._system("/usr/sbin/service swap1 quietstart")
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
        command = '/usr/local/bin/smbpasswd -D 0 -s -a "%s"' % (username)
        smbpasswd = self._pipeopen(command)
        smbpasswd.communicate("%s\n%s\n" % (password, password))
        return smbpasswd.returncode == 0

    def __issue_pwdchange(self, username, command, password):
        self.__pw_with_password(command, password)
        self.__smbpasswd(username, password)

    def user_create(self, username, fullname, password, uid=-1, gid=-1,
                    shell="/sbin/nologin",
                    homedir='/mnt', homedir_mode=0o755,
                    password_disabled=False):
        """Create a user.

        This goes and compiles the invocation needed to execute via pw(8),
        then goes and creates a home directory. Then it goes and adds the
        user via pw(8), and finally adds the user's to the samba user
        database. If adding the user fails for some reason, it will remove
        the directory.

        Required parameters:

        username - a textual identifier for the user (should conform to
                   all constraints with Windows, Unix and OSX usernames).
                   Example: 'root'.
        fullname - a textual 'humanized' identifier for the user. Example:
                   'Charlie Root'.
        password - passphrase used to login to the system; this is
                   ignored if password_disabled is True.

        Optional parameters:

        uid - uid for the user. Defaults to -1 (defaults to the next UID
              via pw(8)).
        gid - gid for the user. Defaults to -1 (defaults to the next GID
              via pw(8)).
        shell - login shell for a user when logging in interactively.
                Defaults to /sbin/nologin.
        homedir - where the user will be put, or /nonexistent if
                  the user doesn't need a directory; defaults to /mnt.
        homedir_mode - mode to use when creating the home directory;
                       defaults to 0755.
        password_disabled - should password based logins be allowed for
                            the user? Defaults to False.

        XXX: the default for the home directory seems like a bad idea.
             Should this be a required parameter instead, or default
             to /var/empty?
        XXX: seems like the password_disabled and password fields could
             be rolled into one property.
        XXX: the homedir mode isn't set today by the GUI; the default
             is set to the FreeBSD default when calling pw(8).
        XXX: smbpasswd errors aren't being caught today.
        XXX: invoking smbpasswd for each user add seems like an
             expensive operation.
        XXX: why are we returning the password hashes?

        Returns:
            A tuple of the user's UID, GID, the Unix encrypted password
            hash, and the encrypted SMB password hash.

        Raises:
            MiddlewareError - tried to create a home directory under a
                              subdirectory on the /mnt memory disk.
            MiddlewareError - failed to create the home directory for
                              the user.
            MiddlewareError - failed to run pw useradd successfully.
        """
        command = '/usr/sbin/pw useradd "%s" -o -c "%s" -d "%s" -s "%s"' % \
            (username, fullname, homedir, shell, )
        if password_disabled:
            command += ' -h -'
        else:
            command += ' -h 0'
        if uid >= 0:
            command += " -u %d" % (uid)
        if gid >= 0:
            command += " -g %d" % (gid)
        if homedir != '/nonexistent':
            # Populate the home directory with files from /usr/share/skel .
            command += ' -m'

        # Is this a new directory or not? Let's not nuke existing directories,
        # e.g. /, /root, /mnt/tank/my-dataset, etc ;).
        new_homedir = False

        if homedir != '/nonexistent':
            # Kept separate for cleanliness between formulating what to do
            # and executing the formulated plan.

            # You're probably wondering why pw -m doesn't suffice. Here's why:
            # 1. pw(8) doesn't create home directories if the base directory
            #    doesn't exist; example: if /mnt/tank/homes doesn't exist and
            #    the user specified /mnt/tank/homes/user, then the home
            #    directory won't be created.
            # 2. pw(8) allows me to specify /mnt/md_size (a regular file) for
            #    the home directory.
            # 3. If some other random path creation error occurs, it's already
            #    too late to roll back the user create.
            try:
                os.makedirs(homedir, mode=homedir_mode)
                if os.stat(homedir).st_dev == os.stat('/mnt').st_dev:
                    # HACK: ensure the user doesn't put their homedir under
                    # /mnt
                    # XXX: fix the GUI code and elsewhere to enforce this, then
                    # remove the hack.
                    raise MiddlewareError('Path for the home directory (%s) '
                                          'must be under a volume or dataset'
                                          % (homedir, ))
            except OSError as oe:
                if oe.errno == errno.EEXIST:
                    if not os.path.isdir(homedir):
                        raise MiddlewareError('Path for home directory already '
                                              'exists and is not a directory')
                else:
                    raise MiddlewareError('Failed to create the home directory '
                                          '(%s) for user: %s'
                                          % (homedir, str(oe)))
            else:
                new_homedir = True

        try:
            self.__issue_pwdchange(username, command, password)
            """
            Make sure to use -d 0 for pdbedit, otherwise it will bomb
            if CIFS debug level is anything different than 'Minimum'
            """
            smb_command = "/usr/local/bin/pdbedit -d 0 -w %s" % username
            smb_cmd = self._pipeopen(smb_command)
            smb_hash = smb_cmd.communicate()[0].split('\n')[0]
        except:
            if new_homedir:
                # Be as atomic as possible when creating the user if
                # commands failed to execute cleanly.
                shutil.rmtree(homedir)
            raise

        user = self.___getpwnam(username)
        return (user.pw_uid, user.pw_gid, user.pw_passwd, smb_hash)

    def group_create(self, name):
        command = '/usr/sbin/pw group add "%s"' % (
            name,
        )
        proc = self._pipeopen(command)
        proc.communicate()
        if proc.returncode != 0:
            raise MiddlewareError(_('Failed to create group %s') % name)
        grnam = self.___getgrnam(name)
        return grnam.gr_gid

    def user_lock(self, username):
        self._system('/usr/local/bin/smbpasswd -d "%s"' % (username))
        self._system('/usr/sbin/pw lock "%s"' % (username))
        return self.user_gethashedpassword(username)

    def user_unlock(self, username):
        self._system('/usr/local/bin/smbpasswd -e "%s"' % (username))
        self._system('/usr/sbin/pw unlock "%s"' % (username))
        return self.user_gethashedpassword(username)

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

    def user_deleteuser(self, username):
        """
        Delete a user using pw(8) utility

        Returns:
            bool
        """
        pipe = self._pipeopen('/usr/sbin/pw userdel "%s"' % (username, ))
        err = pipe.communicate()[1]
        if pipe.returncode != 0:
            log.warn("Failed to delete user %s: %s", username, err)
            return False
        return True

    def user_deletegroup(self, groupname):
        """
        Delete a group using pw(8) utility

        Returns:
            bool
        """
        pipe = self._pipeopen('/usr/sbin/pw groupdel "%s"' % (groupname, ))
        err = pipe.communicate()[1]
        if pipe.returncode != 0:
            log.warn("Failed to delete group %s: %s", groupname, err)
            return False
        return True

    def user_getnextuid(self):
        command = "/usr/sbin/pw usernext"
        pw = self._pipeopen(command)
        uid = pw.communicate()[0]
        if pw.returncode != 0:
            raise ValueError("Could not retrieve usernext")
        uid = uid.split(':')[0]
        return uid

    def user_getnextgid(self):
        command = "/usr/sbin/pw groupnext"
        pw = self._pipeopen(command)
        gid = pw.communicate()[0]
        if pw.returncode != 0:
            raise ValueError("Could not retrieve groupnext")
        return gid

    def save_pubkey(self, homedir, pubkey, username, groupname):
        homedir = str(homedir)
        pubkey = str(pubkey).strip()
        if pubkey:
            pubkey = '%s\n' % pubkey
        sshpath = '%s/.ssh' % (homedir)
        keypath = '%s/.ssh/authorized_keys' % (homedir)
        try:
            oldpubkey = open(keypath).read()
            if oldpubkey == pubkey:
                return
        except:
            pass

        if homedir == '/root':
            self._system("/sbin/mount -uw -o noatime /")
        saved_umask = os.umask(077)
        if not os.path.isdir(sshpath):
            os.makedirs(sshpath)
        if not os.path.isdir(sshpath):
            return  # FIXME: need better error reporting here
        if pubkey == '' and os.path.exists(keypath):
            os.unlink(keypath)
        else:
            fd = open(keypath, 'w')
            fd.write(pubkey)
            fd.close()
            self._system("/usr/sbin/chown -R %s:%s %s" % (username, groupname, sshpath))
        if homedir == '/root':
            self._system("/sbin/mount -ur /")
        os.umask(saved_umask)

    def delete_pubkey(self, homedir):
        homedir = str(homedir)
        keypath = '%s/.ssh/authorized_keys' % (homedir, )
        if os.path.exists(keypath):
            try:
                if homedir == '/root':
                    self._system("/sbin/mount -uw -o noatime /")
                os.unlink(keypath)
            finally:
                if homedir == '/root':
                    self._system("/sbin/mount -ur /")

    def _reload_user(self):
        self._system("/usr/sbin/service ix-passwd quietstart")
        self._system("/usr/sbin/service ix-aliases quietstart")
        self._system("/usr/sbin/service ix-sudoers quietstart")
        self.reload("cifs")

    def winacl_reset(self, path, owner=None, group=None, exclude=None):
        if exclude is None:
            exclude = []

        if isinstance(owner, types.UnicodeType):
            owner = owner.encode('utf-8')

        if isinstance(group, types.UnicodeType):
            group = group.encode('utf-8')

        if isinstance(path, types.UnicodeType):
            path = path.encode('utf-8')

        winacl = os.path.join(path, ACL_WINDOWS_FILE)
        winexists = (ACL.get_acl_ostype(path) == ACL_FLAGS_OS_WINDOWS)
        if not winexists:
            open(winacl, 'a').close()

        script = "/usr/local/bin/winacl"
        args = "-a reset"
        if owner is not None:
            args = "%s -O '%s'" % (args, owner)
        if group is not None:
            args = "%s -G '%s'" % (args, group)
        apply_paths = exclude_path(path, exclude)
        apply_paths = map(lambda y: (y, ' -r '), apply_paths)
        if len(apply_paths) > 1:
            apply_paths.insert(0, (path, ''))
        for apath, flags in apply_paths:
            fargs = args + "%s -p '%s' -x" % (flags, apath)
            cmd = "%s %s" % (script, fargs)
            log.debug("XXX: CMD = %s", cmd)
            self._system(cmd)

    def mp_change_permission(self, path='/mnt', user='root', group='wheel',
                             mode='0755', recursive=False, acl='unix',
                             exclude=None):

        if exclude is None:
            exclude = []

        if isinstance(group, types.UnicodeType):
            group = group.encode('utf-8')

        if isinstance(user, types.UnicodeType):
            user = user.encode('utf-8')

        if isinstance(mode, types.UnicodeType):
            mode = mode.encode('utf-8')

        if isinstance(path, types.UnicodeType):
            path = path.encode('utf-8')

        winacl = os.path.join(path, ACL_WINDOWS_FILE)
        winexists = (ACL.get_acl_ostype(path) == ACL_FLAGS_OS_WINDOWS)
        if acl == 'windows' and not winexists:
            open(winacl, 'a').close()
            winexists = True
        elif acl == 'unix' and winexists:
            os.unlink(winacl)
            winexists = False

        if winexists:
            if not mode:
                mode = '0755'
            script = "/usr/local/bin/winacl"
            args = " -O '%s' -G '%s' -a reset " % (user, group)
            if recursive:
                apply_paths = exclude_path(path, exclude)
                apply_paths = map(lambda y: (y, ' -r '), apply_paths)
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
            if recursive:
                apply_paths = exclude_path(path, exclude)
                apply_paths = map(lambda y: (y, '-R'), apply_paths)
                if len(apply_paths) > 1:
                    apply_paths.insert(0, (path, ''))
            else:
                apply_paths = [(path, '')]
            for apath, flags in apply_paths:
                self._system("/usr/sbin/chown %s '%s':'%s' '%s'" % (flags, user, group, apath))
                self._system("/bin/chmod %s %s '%s'" % (flags, mode, apath))

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
        Create a temporary location for firmware upgrade
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
        Destroy a temporary location for firmware upgrade
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
                ], stderr=f)
                RE_TAR = re.compile(r"^In: (\d+)", re.M | re.S)
                while True:
                    if proc.poll() is not None:
                        break
                    try:
                        os.kill(proc.pid, signal.SIGINFO)
                    except:
                        break
                    time.sleep(1)
                    # TODO: We don't need to read the whole file
                    with open('/tmp/.upgrade_extract', 'r') as f2:
                        line = f2.read()
                    reg = RE_TAR.findall(line)
                    if reg:
                        current = Decimal(reg[-1])
                        percent = (current / size) * 100
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
        try:
            subprocess.check_output(
                                    ['bin/install_worker.sh', 'pre-install'],
                                    stderr=subprocess.STDOUT,
                                    )
        except subprocess.CalledProcessError, cpe:
            raise MiddlewareError('The firmware does not meet the '
                                  'pre-install criteria: %s' % (cpe.output, ))
        finally:
            os.chdir('/')
        # XXX: bleh
        return True

    def apply_update(self, path):
        os.chdir(os.path.dirname(path))
        try:
            subprocess.check_output(
                                    ['bin/install_worker.sh', 'install'],
                                    stderr=subprocess.STDOUT,
                                    )
        except subprocess.CalledProcessError, cpe:
            raise MiddlewareError('The update failed: %s' % (str(cpe), ))
        finally:
            os.chdir('/')
            os.unlink(path)
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

    def get_plugin_upload_path(self):
        from freenasUI.jails.models import JailsConfiguration

        jc = JailsConfiguration.objects.order_by("-id")[0]
        plugin_upload_path = "%s/%s" % (jc.jc_path, ".plugins")

        if not os.path.exists(plugin_upload_path):
            self._system("/bin/mkdir -p %s" % plugin_upload_path)
            self._system("/usr/sbin/chown www:www %s" % plugin_upload_path)
            self._system("/bin/chmod 755 %s" % plugin_upload_path)

        return plugin_upload_path

    def install_pbi(self, pjail, newplugin, pbifile="/var/tmp/firmware/pbifile.pbi"):
        log.debug("install_pbi: pjail = %s", pjail)
        """
        Install a .pbi file into the plugins jail

        Returns:
            bool: installation successful?

        Raises::
            MiddlewareError: pbi_add failed
        """
        from freenasUI.services.models import RPCToken
        from freenasUI.plugins.models import Plugins
        from freenasUI.jails.models import JailsConfiguration
        ret = False

        if 'PATH' in os.environ:
            paths = os.environ['PATH']
            parts = paths.split(':')
            if '/usr/local/sbin' not in parts:
                paths = "%s:%s" % (paths, '/usr/local/sbin')
                os.environ['PATH'] = paths

        open('/tmp/.plugin_upload_install', 'w+').close()

        if not pjail:
            log.debug("install_pbi: pjail is NULL")
            return False

        if not self.pluginjail_running(pjail=pjail):
            log.debug("install_pbi: pjail is is not running")
            return False

        wjail = None
        wlist = Warden().list()
        for wj in wlist:
            wj = WardenJail(**wj)
            if wj.host == pjail:
                wjail = wj
                break

        if wjail is None:
            raise MiddlewareError("The plugins jail is not running, start "
                "it before proceeding")

        jail = None
        for j in Jls():
            if j.hostname == wjail.host:
                jail = j
                break

        # this stuff needs better error checking.. .. ..
        if jail is None:
            raise MiddlewareError("The plugins jail is not running, start "
                "it before proceeding")

        jc = JailsConfiguration.objects.order_by("-id")[0]

        pjail_path = "%s/%s" % (jc.jc_path, wjail.host)
        plugins_path = "%s/%s" % (pjail_path, ".plugins")
        tmpdir = "%s/var/tmp" % pjail_path

        saved_tmpdir = None
        if 'TMPDIR' in os.environ:
            saved_tmpdir = os.environ['TMPDIR']
        os.environ['TMPDIR'] = tmpdir

        log.debug("install_pbi: pjail_path = %s, plugins_path = %s", pjail_path, plugins_path)

        pbi = pbiname = prefix = name = version = arch = None
        p = pbi_add(flags=PBI_ADD_FLAGS_INFO, pbi=pbifile)
        out = p.info(False, -1, 'pbi information for', 'prefix', 'name', 'version', 'arch')

        if not out:
            if saved_tmpdir:
                os.environ['TMPDIR'] = saved_tmpdir
            else:
                del os.environ['TMPDIR']
            raise MiddlewareError("This file was not identified as in PBI "
                "format, it might as well be corrupt.")

        for pair in out:
            (var, val) = pair.split('=', 1)

            var = var.lower()
            if var == 'pbi information for':
                pbiname = val
                pbi = "%s.pbi" % val

            elif var == 'prefix':
                prefix = val

            elif var == 'name':
                name = val

            elif var == 'version':
                version = val

            elif var == 'arch':
                arch = val

        info = pbi_info(flags=PBI_INFO_FLAGS_VERBOSE)
        res = info.run(jail=True, jid=jail.jid)
        if res[0] == 0 and res[1]:
            plugins = re.findall(r'^Name: (?P<name>\w+)$', res[1], re.M)
            if name in plugins:
                # FIXME: do pbi_update instead
                pass

        if pbifile == "/var/tmp/firmware/pbifile.pbi":
            self._system("/bin/mv /var/tmp/firmware/pbifile.pbi %s/%s" % (plugins_path, pbi))

        p = pbi_add(flags=PBI_ADD_FLAGS_NOCHECKSIG | PBI_ADD_FLAGS_FORCE, pbi="%s/%s" %
            ("/.plugins", pbi))
        res = p.run(jail=True, jid=jail.jid)
        if res and res[0] == 0:
            qs = Plugins.objects.filter(plugin_name=name)
            if qs.count() > 0:
                if qs[0].plugin_jail == pjail:
                    log.warn("Plugin named %s already exists in database, "
                             "overwriting.", name)
                    plugin = qs[0]
                else:
                    plugin = Plugins()
            else:
                plugin = Plugins()

            plugin.plugin_path = prefix
            plugin.plugin_enabled = True
            plugin.plugin_ip = jail.ip
            plugin.plugin_name = name
            plugin.plugin_arch = arch
            plugin.plugin_version = version
            plugin.plugin_pbiname = pbiname
            plugin.plugin_jail = wjail.host

            # icky, icky icky, this is how we roll though.
            port = 12345
            qs = Plugins.objects.order_by('-plugin_port')
            if qs.count() > 0:
                port = int(qs[0].plugin_port)

            plugin.plugin_port = port + 1

            """
            Check freenas file within pbi dir for settings
            Currently the API only looks for api_version
            """
            out = Jexec(jid=jail.jid, command="cat %s/freenas" % prefix).run()
            if out and out[0] == 0:
                for line in out[1].splitlines():
                    line = line.strip()
                    if not line:
                        continue

                    key, value = [i.strip() for i in line.split(':', 1)]
                    key = key.lower()
                    value = value.strip()
                    if key in ('api_version', ):
                        setattr(plugin, 'plugin_%s' % (key, ), value)

            rpctoken = RPCToken.new()
            plugin.plugin_secret = rpctoken

            plugin_path = "%s/%s" % (pjail_path, plugin.plugin_path)
            oauth_file = "%s/%s" % (plugin_path, ".oauth")

            log.debug("install_pbi: plugin_path = %s, oauth_file = %s",
                plugin_path, oauth_file)

            fd = os.open(oauth_file, os.O_WRONLY | os.O_CREAT, 0600)
            os.write(fd, "key = %s\n" % rpctoken.key)
            os.write(fd, "secret = %s\n" % rpctoken.secret)
            os.close(fd)

            try:
                log.debug("install_pbi: trying to save plugin to database")
                plugin.save()
                newplugin.append(plugin)
                log.debug("install_pbi: plugin saved to database")
                ret = True
            except Exception, e:
                log.debug("install_pbi: FAIL! %s", e)
                ret = False

        elif res and res[0] != 0:
            # pbid seems to return 255 for any kind of error
            # lets use error str output to find out what happenned
            if re.search(r'failed checksum', res[1], re.I | re.S | re.M):
                raise MiddlewareError("The file %s seems to be "
                    "corrupt, please try download it again." % (
                        pbiname,
                        )
                    )
            if saved_tmpdir:
                os.environ['TMPDIR'] = saved_tmpdir
            raise MiddlewareError(p.error)

        log.debug("install_pbi: everything went well, returning %s", ret)
        if saved_tmpdir:
            os.environ['TMPDIR'] = saved_tmpdir
        else:
            del os.environ['TMPDIR']
        return ret

    def _get_pbi_info(self, pbifile):
        pbi = pbiname = prefix = name = version = arch = None

        p = pbi_add(flags=PBI_ADD_FLAGS_INFO, pbi=pbifile)
        out = p.info(False, -1, 'pbi information for', 'prefix', 'name', 'version', 'arch')

        if not out:
            raise MiddlewareError("This file was not identified as in PBI "
                "format, it might as well be corrupt.")

        for pair in out:
            (var, val) = pair.split('=', 1)
            log.debug("XXX: var = %s, val = %s", var, val)

            var = var.lower()
            if var == 'pbi information for':
                pbiname = val
                pbi = "%s.pbi" % val

            elif var == 'prefix':
                prefix = val

            elif var == 'name':
                name = val

            elif var == 'version':
                version = val

            elif var == 'arch':
                arch = val

        return pbi, pbiname, prefix, name, version, arch

    def _get_plugin_info(self, name):
        from freenasUI.plugins.models import Plugins
        plugin = None

        qs = Plugins.objects.filter(plugin_name__iexact=name)
        if qs.count() > 0:
            plugin = qs[0]

        return plugin

    def update_pbi(self, plugin=None):
        from freenasUI.jails.models import JailsConfiguration, JailMountPoint
        from freenasUI.services.models import RPCToken
        from freenasUI.common.pipesubr import pipeopen
        ret = False

        if not plugin:
            raise MiddlewareError("plugin could not be found and is NULL")

        if 'PATH' in os.environ:
            paths = os.environ['PATH']
            parts = paths.split(':')
            if '/usr/local/sbin' not in parts:
                paths = "%s:%s" % (paths, '/usr/local/sbin')
                os.environ['PATH'] = paths

        log.debug("XXX: update_pbi: starting")

        open('/tmp/.plugin_upload_update', 'w+').close()

        if not plugin:
            raise MiddlewareError("plugin is NULL")

        (c, conn) = self.__open_db(ret_conn=True)
        c.execute("SELECT plugin_jail FROM plugins_plugins WHERE id = %d" % plugin.id)
        row = c.fetchone()
        if not row:
            log.debug("update_pbi: plugins plugin not in database")
            return False

        jail_name = row[0]

        jail = None
        for j in Jls():
            if j.hostname == jail_name:
                jail = j
                break

        if jail is None:
            return ret

        jc = JailsConfiguration.objects.order_by("-id")[0]

        mountpoints = JailMountPoint.objects.filter(jail=jail_name)
        for mp in mountpoints:
            fp = "%s/%s%s" % (jc.jc_path, jail_name, mp.destination)
            p = pipeopen("/sbin/umount -f '%s'" % fp)
            out = p.communicate()
            if p.returncode != 0:
                raise MiddlewareError(out[1])

        jail_root = jc.jc_path
        jail_path = "%s/%s" % (jail_root, jail_name)
        plugins_path = "%s/%s" % (jail_path, ".plugins")

        # Get new PBI settings
        newpbi, newpbiname, newprefix, newname, newversion, newarch = self._get_pbi_info(
            "/var/tmp/firmware/pbifile.pbi")

        log.debug("XXX: newpbi = %s", newpbi)
        log.debug("XXX: newpbiname = %s", newpbiname)
        log.debug("XXX: newprefix = %s", newprefix)
        log.debug("XXX: newname = %s", newname)
        log.debug("XXX: newversion = %s", newversion)
        log.debug("XXX: newarch = %s", newarch)

        pbitemp = "/var/tmp/pbi"
        oldpbitemp = "%s/old" % pbitemp
        newpbitemp = "%s/new" % pbitemp

        newpbifile = "%s/%s" % (plugins_path, newpbi)
        oldpbifile = "%s/%s.pbi" % (plugins_path, plugin.plugin_pbiname)

        log.debug("XXX: oldpbifile = %s", oldpbifile)
        log.debug("XXX: newpbifile = %s", newpbifile)

        # Rename PBI to it's actual name
        self._system("/bin/mv /var/tmp/firmware/pbifile.pbi %s" % newpbifile)

        # Create a temporary directory to place old, new, and PBI patch files
        out = Jexec(jid=jail.jid, command="/bin/mkdir -p %s" % oldpbitemp).run()
        out = Jexec(jid=jail.jid, command="/bin/mkdir -p %s" % newpbitemp).run()
        out = Jexec(jid=jail.jid, command="/bin/rm -f %s/*" % pbitemp).run()
        if out[0] != 0:
            raise MiddlewareError("There was a problem cleaning up the "
                "PBI temp dirctory")

        pbiname = newpbiname
        oldpbiname = "%s.pbi" % plugin.plugin_pbiname
        newpbiname = "%s.pbi" % newpbiname

        log.debug("XXX: oldpbiname = %s", oldpbiname)
        log.debug("XXX: newpbiname = %s", newpbiname)

        self.umount_filesystems_within("%s%s" % (jail_path, newprefix))

        # Create a PBI from the installed version
        p = pbi_create(flags=PBI_CREATE_FLAGS_BACKUP | PBI_CREATE_FLAGS_OUTDIR,
            outdir=oldpbitemp, pbidir=plugin.plugin_pbiname)
        out = p.run(True, jail.jid)
        if out[0] != 0:
            raise MiddlewareError("There was a problem creating the PBI")

        # Copy the old PBI over to our temporary PBI workspace
        out = Jexec(jid=jail.jid, command="/bin/cp %s/%s /.plugins/old.%s" % (
            oldpbitemp, oldpbiname, oldpbiname)).run()
        if out[0] != 0:
            raise MiddlewareError("Unable to copy old PBI file to plugins directory")

        oldpbifile = "%s/%s" % (oldpbitemp, oldpbiname)
        newpbifile = "%s/%s" % (newpbitemp, newpbiname)

        log.debug("XXX: oldpbifile = %s", oldpbifile)
        log.debug("XXX: newpbifile = %s", newpbifile)

        # Copy the new PBI over to our temporary PBI workspace
        out = Jexec(jid=jail.jid, command="/bin/cp /.plugins/%s %s/" % (
            newpbiname, newpbitemp)).run()
        if out[0] != 0:
            raise MiddlewareError("Unable to copy new PBI file to plugins directory")

        # Now we make the patch for the PBI upgrade
        p = pbi_makepatch(flags=PBI_MAKEPATCH_FLAGS_OUTDIR | PBI_MAKEPATCH_FLAGS_NOCHECKSIG,
            outdir=pbitemp, oldpbi=oldpbifile, newpbi=newpbifile)
        out = p.run(True, jail.jid)
        if out[0] != 0:
            raise MiddlewareError("Unable to make a PBI patch")

        pbpfile = "%s-%s_to_%s-%s.pbp" % (plugin.plugin_name.lower(),
            plugin.plugin_version, newversion, plugin.plugin_arch)

        log.debug("XXX: pbpfile = %s", pbpfile)

        fullpbppath = "%s/%s/%s" % (jail_path, pbitemp, pbpfile)
        log.debug("XXX: fullpbppath = %s", fullpbppath)

        if not os.access(fullpbppath, os.F_OK):
            raise MiddlewareError("Unable to create PBP file")

        # Apply the upgrade patch to upgrade the PBI to the new version
        p = pbi_patch(flags=PBI_PATCH_FLAGS_OUTDIR | PBI_PATCH_FLAGS_NOCHECKSIG,
            outdir=pbitemp, pbp="%s/%s" % (pbitemp, pbpfile))
        out = p.run(True, jail.jid)
        if out[0] != 0:
            raise MiddlewareError("Unable to patch the PBI")

        # Update the database with the new PBI version
        plugin.plugin_path = newprefix
        plugin.plugin_name = newname
        plugin.plugin_arch = newarch
        plugin.plugin_version = newversion
        plugin.plugin_pbiname = pbiname

        try:
            log.debug("XXX: plugin.save()")
            plugin.save()
            ret = True
            log.debug("XXX: plugin.save(), WE ARE GOOD.")

        except Exception as e:
            raise MiddlewareError(_(e))

        rpctoken = RPCToken.objects.filter(pk=plugin.id)
        if not rpctoken:
            raise MiddlewareError(_("No RPC Token!"))
        rpctoken = rpctoken[0]

        plugin_path = "%s/%s" % (jail_path, plugin.plugin_path)
        oauth_file = "%s/%s" % (plugin_path, ".oauth")

        log.debug("update_pbi: plugin_path = %s, oauth_file = %s",
            plugin_path, oauth_file)

        fd = os.open(oauth_file, os.O_WRONLY | os.O_CREAT, 0600)
        os.write(fd, "key = %s\n" % rpctoken.key)
        os.write(fd, "secret = %s\n" % rpctoken.secret)
        os.close(fd)

        self._system("/usr/sbin/service ix-plugins forcestop %s:%s" % (jail, newname))
        self._system("/usr/sbin/service ix-plugins forcestart %s:%s" % (jail, newname))

        for mp in mountpoints:
            fp = "%s/%s%s" % (jc.jc_path, jail_name, mp.destination)
            p = pipeopen("/sbin/mount_nullfs '%s' '%s'" % (mp.source, fp))
            out = p.communicate()
            if p.returncode != 0:
                raise MiddlewareError(out[1])

        log.debug("XXX: update_pbi: returning %s", ret)
        return ret

    def delete_pbi(self, plugin):
        ret = False

        if not plugin.id:
            log.debug("delete_pbi: plugins plugin not in database")
            return False

        jail_name = plugin.plugin_jail

        jail = None
        for j in Jls():
            if j.hostname == jail_name:
                jail = j
                break

        if jail is None:
            return ret

        jail_path = j.path

        info = pbi_info(flags=PBI_INFO_FLAGS_VERBOSE)
        res = info.run(jail=True, jid=jail.jid)
        plugins = re.findall(r'^Name: (?P<name>\w+)$', res[1], re.M)

        # Plugin is not installed in the jail at all
        if res[0] == 0 and plugin.plugin_name not in plugins:
            return True

        pbi_path = os.path.join(
            jail_path,
            jail_name,
            "usr/pbi",
            "%s-%s" % (plugin.plugin_name, platform.machine()),
            )
        self.umount_filesystems_within(pbi_path)

        p = pbi_delete(pbi=plugin.plugin_pbiname)
        res = p.run(jail=True, jid=jail.jid)
        if res and res[0] == 0:
            try:
                plugin.delete()
                ret = True

            except Exception, err:
                log.debug("delete_pbi: unable to delete pbi %s from database (%s)", plugin, err)
                ret = False

        return ret

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

        (c, conn) = self.__open_db(ret_conn=True)
        c.execute("SELECT jc_path FROM jails_jailsconfiguration LIMIT 1")
        row = c.fetchone()
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

    def delete_plugins(self):
        from freenasUI.plugins.models import Plugins
        for p in Plugins.objects.all():
            p.delete()

    def get_volume_status(self, name, fs):
        status = 'UNKNOWN'
        if fs == 'ZFS':
            p1 = self._pipeopen('zpool list -H -o health %s' % str(name))
            if p1.wait() == 0:
                status = p1.communicate()[0].strip('\n')
        elif fs == 'UFS':

            provider = self.get_label_consumer('ufs', name)
            if provider is None:
                return 'UNKNOWN'
            gtype = provider.xpath("../../name")[0].text

            if gtype in ('MIRROR', 'STRIPE', 'RAID3'):

                search = provider.xpath("../config/State")
                if len(search) > 0:
                    status = search[0].text

            else:
                p1 = self._pipeopen('mount|grep "/dev/ufs/%s"' % (name, ))
                p1.communicate()
                if p1.returncode == 0:
                    status = 'HEALTHY'
                else:
                    status = 'DEGRADED'

        if status in ('UP', 'COMPLETE', 'ONLINE'):
            status = 'HEALTHY'
        return status

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

        return disksd

    def get_partitions(self, try_disks=True):
        disks = self.get_disks().keys()
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
                p1 = Popen(["/usr/sbin/diskinfo", part], stdin=PIPE, stdout=PIPE)
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

    def detect_volumes(self, extra=None):
        """
        Responsible to detect existing volumes by running
        g{mirror,stripe,raid3},zpool commands

        Used by: Automatic Volume Import
        """

        volumes = []
        doc = self._geom_confxml()
        # Detect GEOM mirror, stripe and raid3
        for geom in ('mirror', 'stripe', 'raid3'):
            search = doc.xpath("//class[name = '%s']/geom/config" % (geom.upper(),))
            for entry in search:
                label = entry.xpath('../name')[0].text
                disks = []
                for consumer in entry.xpath('../consumer/provider'):
                    provider = consumer.attrib.get('ref')
                    device = doc.xpath("//class[name = 'DISK']//provider[@id = '%s']/name" % provider)
                    # The raid might be degraded
                    if len(device) > 0:
                        disks.append({'name': device[0].text})

                # Next thing is find out whether this is a raw block device or has GPT
                # TODO: MBR?
                search = doc.xpath("//class[name = 'PART']/geom[name = '%s/%s']/provider//config[type = 'freebsd-ufs']" % (geom, label))
                if len(search) > 0:
                    label = search[0].xpath("../name")[0].text.split('/', 1)[1]
                volumes.append({
                    'label': label,
                    'type': 'geom',
                    'group_type': geom,
                    'disks': {'vdevs': [{'disks': disks, 'name': geom}]},
                    })

        pool_name = re.compile(r'pool: (?P<name>%s).*?id: (?P<id>\d+)' % (zfs.ZPOOL_NAME_RE, ), re.I | re.M | re.S)
        p1 = self._pipeopen("zpool import")
        res = p1.communicate()[0]

        for pool, zid in pool_name.findall(res):
            # get status part of the pool
            status = res.split('id: %s\n' % zid)[1].split('pool:')[0]
            try:
                roots = zfs.parse_status(pool, doc, 'id: %s\n%s' % (zid, status))
            except Exception, e:
                log.warn("Error parsing %s: %s", pool, e)
                continue

            if roots['data'].status != 'UNAVAIL':
                volumes.append({
                    'label': pool,
                    'type': 'zfs',
                    'id': roots.id,
                    'group_type': 'none',
                    'cache': roots['cache'].dump() if roots['cache'] else None,
                    'log': roots['logs'].dump() if roots['logs'] else None,
                    'spare': roots['spares'].dump() if roots['spares'] else None,
                    'disks': roots['data'].dump(),
                    })

        return volumes

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

    def _encvolume_detach(self, volume):
        """Detach GELI providers after detaching volume."""
        """See bug: #3964"""
        if volume.vol_encrypt > 0:
            for ed in volume.encrypteddisk_set.all():
                self.geli_detach(ed.encrypted_provider)

    def volume_detach(self, volume):
        """Detach a volume from the system

        This either executes exports a zpool or umounts a generic volume (e.g.
        NTFS, UFS, etc).

        In the event that the volume is still in use in the OS, the end-result
        is implementation defined depending on the filesystem, and the set of
        commands used to export the filesystem.

        Finally, this method goes and cleans up the mountpoint. This is a
        sanity check to ensure that things are in synch.

        XXX: recursive unmounting / needs for recursive unmounting here might
             be a good idea.
        XXX: better feedback about files in use might be a good idea...
             someday. But probably before getting to this point. This is a
             tricky problem to fix in a way that doesn't unnecessarily suck up
             resources, but also ensures that the user is provided with
             meaningful data.
        XXX: this doesn't work with the alternate mountpoint functionality
             available in UFS volumes.

        Parameters:
            vol_name: a textual name for the volume, e.g. tank, stripe, etc.
            vol_fstype: the filesystem type for the volume; valid values are:
                        'EXT2FS', 'MSDOSFS', 'UFS', 'ZFS'.

        Raises:
            MiddlewareError: the volume could not be detached cleanly.
            MiddlewareError: the volume's mountpoint couldn't be removed.
        """

        vol_name = volume.vol_name
        vol_fstype = volume.vol_fstype

        succeeded = False
        provider = None

        vol_mountpath = self.__get_mountpath(vol_name, vol_fstype)
        if vol_fstype == 'ZFS':
            cmd = 'zpool export %s' % (vol_name)
            cmdf = 'zpool export -f %s' % (vol_name)
        else:
            cmd = 'umount %s' % (vol_mountpath)
            cmdf = 'umount -f %s' % (vol_mountpath)
            provider = self.get_label_consumer('ufs', vol_name)

        self.stop("syslogd")

        p1 = self._pipeopen(cmd)
        stdout, stderr = p1.communicate()
        if p1.returncode == 0:
            succeeded = True
        else:
            p1 = self._pipeopen(cmdf)
            stdout, stderr = p1.communicate()

        if vol_fstype != 'ZFS':
            geom_type = provider.xpath("../../name")[0].text.lower()
            if geom_type in ('mirror', 'stripe', 'raid3'):
                g_name = provider.xpath("../name")[0].text
                self._system("geom %s stop %s" % (geom_type, g_name))

        self.start("syslogd")

        if not succeeded and p1.returncode:
            raise MiddlewareError('Failed to detach %s with "%s" (exited '
                                  'with %d): %s' %
                                  (vol_name, cmd, p1.returncode, stderr))

        self._encvolume_detach(volume)
        self.__rmdir_mountpoint(vol_mountpath)

    def __rmdir_mountpoint(self, path):
        """Remove a mountpoint directory designated by path

        This only nukes mountpoints that exist in /mnt as alternate mointpoints
        can be specified with UFS, which can take down mission critical
        subsystems.

        This purposely doesn't use shutil.rmtree to avoid removing files that
        were potentially hidden by the mount.

        Parameters:
            path: a path suffixed with /mnt that points to a mountpoint that
                  needs to be nuked.

        XXX: rewrite to work outside of /mnt and handle unmounting of
             non-critical filesystems.
        XXX: remove hardcoded reference to /mnt .

        Raises:
            MiddlewareError: the volume's mountpoint couldn't be removed.
        """

        if path.startswith('/mnt'):
            # UFS can be mounted anywhere. Don't nuke /etc, /var, etc as the
            # underlying contents might contain something of value needed for
            # the system to continue operating.
            try:
                if os.path.isdir(path):
                    os.rmdir(path)
            except OSError as ose:
                raise MiddlewareError('Failed to remove mountpoint %s: %s'
                                      % (path, str(ose), ))

    def zfs_scrub(self, name, stop=False):
        if stop:
            imp = self._pipeopen('zpool scrub -s %s' % str(name))
        else:
            imp = self._pipeopen('zpool scrub %s' % str(name))
        stdout, stderr = imp.communicate()
        if imp.returncode != 0:
            raise MiddlewareError('Unable to scrub %s: %s' % (name, stderr))
        return True

    def zfs_snapshot_list(self, path=None, replications=None):
        fsinfo = dict()

        zfsproc = self._pipeopen("/sbin/zfs list -t volume -o name -H")
        zvols = filter(lambda y: y != '', zfsproc.communicate()[0].split('\n'))

        if path:
            zfsproc = self._pipeopen("/sbin/zfs list -r -t snapshot -H -S creation '%s'" % path)
        else:
            zfsproc = self._pipeopen("/sbin/zfs list -t snapshot -H -S creation")
        lines = zfsproc.communicate()[0].split('\n')
        for line in lines:
            if line != '':
                list = line.split('\t')
                snapname = list[0]
                used = list[1]
                refer = list[3]
                fs, name = snapname.split('@')
                try:
                    snaplist = fsinfo[fs]
                    mostrecent = False
                except:
                    snaplist = []
                    mostrecent = True
                replication = None
                if replications:
                    for repl, snaps in replications.iteritems():
                        remotename = '%s@%s' % (
                            fs.replace(
                                repl.repl_filesystem + '@',
                                repl.repl_zfs + '@',
                            ),
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
                        replication=replication
                    ))
                fsinfo[fs] = snaplist
        return fsinfo

    def zfs_mksnap(self, dataset, name, recursive=False):
        if recursive:
            p1 = self._pipeopen("/sbin/zfs snapshot -r '%s'@'%s'" % (dataset, name))
        else:
            p1 = self._pipeopen("/sbin/zfs snapshot '%s'@'%s'" % (dataset, name))
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
                cur.execute("""SELECT name FROM sqlite_master
        WHERE type='table'
        ORDER BY name;""")
            finally:
                conn.close()
        except:
            os.unlink(config_file_name)
            return False

        shutil.move(config_file_name, '/data/uploaded.db')
        # Now we must run the migrate operation in the case the db is older
        open(NEED_UPDATE_SENTINEL, 'w+').close()

        return True

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
            if (not data[1] in noinherit_fields) and (data[3] == 'default' or data[3].startswith('inherited')):
                dval[data[1]] = "inherit"
            else:
                dval[data[1]] = data[2]
        return retval

    def zfs_set_option(self, name, item, value):
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

    def zfs_dataset_release_snapshots(self, name, recursive=False):
        name = str(name)
        retval = None
        if recursive:
            zfscmd = "/sbin/zfs list -Ht snapshot -o name,freenas:state -r '%s'" % (name)
        else:
            zfscmd = "/sbin/zfs list -Ht snapshot -o name,freenas:state -r -d 1 '%s'" % (name)
        try:
            with mntlock(blocking=False):
                zfsproc = self._pipeopen(zfscmd)
                output = zfsproc.communicate()[0]
                if output != '':
                    snapshots_list = output.splitlines()
                for snapshot_item in filter(None, snapshots_list):
                    snapshot, state = snapshot_item.split('\t')
                    if state != '-':
                        self.zfs_inherit_option(snapshot, 'freenas:state')
                        self._system("/sbin/zfs release -r freenas:repl %s" % (snapshot))
        except IOError:
            retval = 'Try again later.'
        return retval

    # Reactivate replication on all snapshots
    def zfs_dataset_reset_replicated_snapshots(self, name, recursive=False):
        name = str(name)
        retval = None
        if recursive:
            zfscmd = "/sbin/zfs list -Ht snapshot -o name,freenas:state -r '%s'" % (name)
        else:
            zfscmd = "/sbin/zfs list -Ht snapshot -o name,freenas:state -r -d 1 '%s'" % (name)
        try:
            with mntlock(blocking=False):
                zfsproc = self._pipeopen(zfscmd)
                output = zfsproc.communicate()[0]
                if output != '':
                    snapshots_list = output.splitlines()
                for snapshot_item in filter(None, snapshots_list):
                    snapshot, state = snapshot_item.split('\t')
                    if state != 'NEW':
                        self.zfs_set_option(snapshot, 'freenas:state', 'NEW')
                        self._system("/sbin/zfs hold -r freenas:repl %s" % (snapshot))
        except IOError:
            retval = 'Try again later.'
        return retval

    def geom_disk_replace(self, volume, to_disk):
        """Replace disk in ``volume`` for ``to_disk``

        Raises:
            ValueError: Volume not found

        Returns:
            0 if the disk was replaced, > 0 otherwise
        """

        assert volume.vol_fstype == 'UFS'

        provider = self.get_label_consumer('ufs', volume.vol_name)
        if provider is None:
            raise ValueError("UFS Volume %s not found" % (volume.vol_name,))
        class_name = provider.xpath("../../name")[0].text
        geom_name = provider.xpath("../name")[0].text

        if class_name == "MIRROR":
            rv = self._system_nolog("geom mirror forget %s" % (geom_name,))
            if rv != 0:
                return rv
            p1 = self._pipeopen("geom mirror insert %s /dev/%s" % (str(geom_name), str(to_disk),))
            stdout, stderr = p1.communicate()
            if p1.returncode != 0:
                error = ", ".join(stderr.split('\n'))
                raise MiddlewareError('Replacement failed: "%s"' % error)
            return 0

        elif class_name == "RAID3":
            numbers = provider.xpath("../consumer/config/Number")
            ncomponents = int(provider.xpath("../config/Components")[0].text)
            numbers = [int(node.text) for node in numbers]
            lacking = [x for x in xrange(ncomponents) if x not in numbers][0]
            p1 = self._pipeopen("geom raid3 insert -n %d %s %s" %
                                        (lacking, str(geom_name), str(to_disk),))
            stdout, stderr = p1.communicate()
            if p1.returncode != 0:
                error = ", ".join(stderr.split('\n'))
                raise MiddlewareError('Replacement failed: "%s"' % error)
            return 0

        return 1

    def iface_destroy(self, name):
        self._system("ifconfig %s destroy" % name)

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

                portsok = len(filter(
                    lambda y: y == 'ACTIVE,COLLECTING,DISTRIBUTING',
                    ports
                ))
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

    def interface_mtu(self, iface, mtu):
        self._system("ifconfig %s mtu %s" % (iface, mtu))

    def guess_default_interface(self):
        p1 = self._pipeopen("route get default | grep 'interface:' | awk '{ print $2 }'")
        iface = p1.communicate()
        if p1.returncode != 0:
            iface = None
        try:
            iface = iface[0].strip()
        except:
            pass
        return iface

    def lagg_remove_port(self, lagg, iface):
        return self._system_nolog("ifconfig %s -laggport %s" % (lagg, iface))

    def __init__(self):
        self.__confxml = None
        self.__camcontrol = None
        self.__diskserial = {}
        self.__twcli = {}

    def __del__(self):
        self.__confxml = None

    def _geom_confxml(self):
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

    def serial_from_device(self, devname):
        if devname in self.__diskserial:
            return self.__diskserial.get(devname)

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

        p1 = Popen(["/usr/local/sbin/smartctl", "-i"] + args, stdout=PIPE)
        output = p1.communicate()[0]
        search = re.search(r'Serial Number:\s+(?P<serial>.+)', output, re.I)
        if search:
            serial = search.group("serial")
            self.__diskserial[devname] = serial
            return serial
        return None

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

    def device_to_identifier(self, name):
        name = str(name)
        doc = self._geom_confxml()

        serial = self.serial_from_device(name)
        if serial:
            return "{serial}%s" % serial

        search = doc.xpath("//class[name = 'PART']/..//*[name = '%s']//config[type = 'freebsd-zfs']/rawuuid" % name)
        if len(search) > 0:
            return "{uuid}%s" % search[0].text
        search = doc.xpath("//class[name = 'PART']/geom/..//*[name = '%s']//config[type = 'freebsd-ufs']/rawuuid" % name)
        if len(search) > 0:
            return "{uuid}%s" % search[0].text

        search = doc.xpath("//class[name = 'LABEL']/geom[name = '%s']/provider/name" % name)
        if len(search) > 0:
            return "{label}%s" % search[0].text

        search = doc.xpath("//class[name = 'DEV']/geom[name = '%s']" % name)
        if len(search) > 0:
            return "{devicename}%s" % name

        return ''

    def identifier_to_device(self, ident):

        if not ident:
            return None

        doc = self._geom_confxml()

        search = re.search(r'\{(?P<type>.+?)\}(?P<value>.+)', ident)
        if not search:
            return None

        tp = search.group("type")
        value = search.group("value")

        if tp == 'uuid':
            search = doc.xpath("//class[name = 'PART']/geom//config[rawuuid = '%s']/../../name" % value)
            if len(search) > 0:
                for entry in search:
                    if not entry.text.startswith('label'):
                        return entry.text
            return None

        elif tp == 'label':
            search = doc.xpath("//class[name = 'LABEL']/geom//provider[name = '%s']/../name" % value)
            if len(search) > 0:
                return search[0].text
            return None

        elif tp == 'serial':
            for devname in self.__get_disks():
                serial = self.serial_from_device(devname)
                if serial == value:
                    return devname
            return None

        elif tp == 'devicename':
            search = doc.xpath("//class[name = 'DEV']/geom[name = '%s']" % value)
            if len(search) > 0:
                return value
            return None
        else:
            raise NotImplementedError

    def part_type_from_device(self, name, device):
        """
        Given a partition a type and a disk name (adaX)
        get the first partition that matches the type
        """
        doc = self._geom_confxml()
        # TODO get from MBR as well?
        search = doc.xpath("//class[name = 'PART']/geom[name = '%s']//config[type = 'freebsd-%s']/../name" % (device, name))
        if len(search) > 0:
            return search[0].text
        else:
            return ''

    def swap_from_diskid(self, diskid):
        from freenasUI.storage.models import Disk
        disk = Disk.objects.get(id=diskid)
        return self.part_type_from_device('swap', disk.devname)

    def swap_from_identifier(self, ident):
        return self.part_type_from_device('swap', self.identifier_to_device(ident))

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

    def zpool_scrubbing(self):
        p1 = self._pipeopen("zpool status")
        res = p1.communicate()[0]
        r = re.compile(r'scan: (resilver|scrub) in progress')
        return r.search(res) is not None

    def zpool_version(self, name):
        p1 = self._pipeopen("zpool get -H -o value version %s" % name)
        res, err = p1.communicate()
        if p1.returncode != 0:
            raise ValueError(err)
        res = res[0].strip('\n')
        try:
            return int(res)
        except:
            return res

    def zpool_upgrade(self, name):
        p1 = self._pipeopen("zpool upgrade %s" % name)
        res = p1.communicate()[0]
        if p1.returncode == 0:
            return True
        return res

    def _camcontrol_list(self):
        """
        Parse camcontrol devlist -v output to gather
        controller id, channel no and driver from a device

        Returns:
            dict(devname) = dict(drv, controller, channel)
        """
        if self.__camcontrol is not None:
            return self.__camcontrol

        self.__camcontrol = {}

        """
        Hacky workaround

        It is known that at least some HPT controller have a bug in the
        camcontrol devlist output with multiple controllers, all controllers
        will be presented with the same driver with index 0
        e.g. two hpt27xx0 instead of hpt27xx0 and hpt27xx1

        What we do here is increase the controller id by its order of
        appearance in the camcontrol output
        """
        hptctlr = defaultdict(int)

        re_drv_cid = re.compile(r'.* on (?P<drv>.*?)(?P<cid>[0-9]+) bus', re.S | re.M)
        re_tgt = re.compile(r'target (?P<tgt>[0-9]+) .*?lun (?P<lun>[0-9]+) .*\((?P<dv1>[a-z]+[0-9]+),(?P<dv2>[a-z]+[0-9]+)\)', re.S | re.M)
        drv, cid, tgt, lun, dev, devtmp = (None, ) * 6

        proc = self._pipeopen("camcontrol devlist -v")
        for line in proc.communicate()[0].splitlines():
            if not line.startswith('<'):
                reg = re_drv_cid.search(line)
                if not reg:
                    continue
                drv = reg.group("drv")
                if drv.startswith("hpt"):
                    cid = hptctlr[drv]
                    hptctlr[drv] += 1
                else:
                    cid = reg.group("cid")
            else:
                reg = re_tgt.search(line)
                if not reg:
                    continue
                tgt = reg.group("tgt")
                lun = reg.group("lun")
                dev = reg.group("dv1")
                devtmp = reg.group("dv2")
                if dev.startswith("pass"):
                    dev = devtmp
                self.__camcontrol[dev] = {
                    'drv': drv,
                    'controller': int(cid),
                    'channel': int(tgt),
                    'lun': int(lun)
                    }
        return self.__camcontrol

    def sync_disk(self, devname):
        from freenasUI.storage.models import Disk

        # Do not sync geom classes like multipath/hast/etc
        if devname.find("/") != -1:
            return

        doc = self._geom_confxml()
        self.__diskserial.clear()
        self.__camcontrol = None

        ident = self.device_to_identifier(devname)
        qs = Disk.objects.filter(disk_identifier=ident).order_by('disk_enabled')
        if ident and qs.exists():
            disk = qs[0]
        else:
            qs = Disk.objects.filter(disk_name=devname).update(
                disk_enabled=False
            )
            disk = Disk()
            disk.disk_identifier = ident
        disk.disk_name = devname
        disk.disk_enabled = True
        disk.disk_serial = self.serial_from_device(devname) or ''
        reg = RE_DSKNAME.search(devname)
        if reg:
            disk.disk_subsystem = reg.group(1)
            disk.disk_number = int(reg.group(2))
        mediasize = doc.xpath("//class[name = 'DISK']//geom[name = '%s']/provider/mediasize" % devname)
        if mediasize:
            disk.disk_size = mediasize[0].text
        disk.save()

    def sync_disk_extra(self, disk, add=False):
        return

    def sync_disks(self):
        from freenasUI.storage.models import Disk

        doc = self._geom_confxml()
        disks = self.__get_disks()
        self.__diskserial.clear()
        self.__camcontrol = None

        in_disks = {}
        serials = []
        for disk in Disk.objects.order_by('disk_enabled'):

            dskname = self.identifier_to_device(disk.disk_identifier)
            if not dskname or dskname in in_disks:
                # If we cant translate the indentifier to a device, give up
                # If dskname has already been seen once then we are probably
                # dealing with with multipath here
                disk.delete()
                continue
            else:
                disk.disk_enabled = True
                if dskname != disk.disk_name:
                    disk.disk_name = dskname

            reg = RE_DSKNAME.search(dskname)
            if reg:
                disk.disk_subsystem = reg.group(1)
                disk.disk_number = int(reg.group(2))

            if disk.disk_serial:
                serials.append(disk.disk_serial)

            mediasize = doc.xpath("//class[name = 'DISK']//geom[name = '%s']/provider/mediasize" % dskname)
            if mediasize:
                disk.disk_size = mediasize[0].text

            self.sync_disk_extra(disk, add=False)

            if dskname not in disks:
                disk.disk_enabled = False
                if disk._original_state.get("disk_enabled"):
                    disk.save()
                else:
                    # Duplicated disk entries in database
                    disk.delete()
            else:
                disk.save()
            in_disks[dskname] = disk

        for disk in disks:
            if disk not in in_disks:
                d = Disk()
                d.disk_name = disk
                d.disk_identifier = self.device_to_identifier(disk)
                d.disk_serial = self.serial_from_device(disk) or ''
                mediasize = doc.xpath("//class[name = 'DISK']//geom[name = '%s']/provider/mediasize" % disk)
                if mediasize:
                    d.disk_size = mediasize[0].text
                if d.disk_serial:
                    if d.disk_serial in serials:
                        # Probably dealing with multipath here, do not add another
                        continue
                    else:
                        serials.append(d.disk_serial)
                reg = RE_DSKNAME.search(disk)
                if reg:
                    d.disk_subsystem = reg.group(1)
                    d.disk_number = int(reg.group(2))
                self.sync_disk_extra(d, add=True)
                d.save()

    def sync_encrypted(self, volume=None):
        """
        This syncs the EncryptedDisk table with the current state
        of a volume
        """
        from freenasUI.storage.models import Disk, EncryptedDisk, Volume
        if volume is not None:
            volumes = [volume]
        else:
            volumes = Volume.objects.filter(vol_encrypt__gt=0)

        for vol in volumes:
            """
            Parse zpool status to get encrypted providers
            """
            zpool = self.zpool_parse(vol.vol_name)
            provs = []
            for dev in zpool.get_devs():
                if not dev.name.endswith(".eli"):
                    continue
                prov = dev.name[:-4]
                qs = EncryptedDisk.objects.filter(encrypted_provider=prov)
                if not qs.exists():
                    ed = EncryptedDisk()
                    ed.encrypted_volume = vol
                    ed.encrypted_provider = dev[:-4]
                    disk = Disk.objects.filter(disk_name=dev.disk, disk_enabled=True)
                    if disk.exists():
                        disk = disk[0]
                    else:
                        log.error("Could not find Disk entry for %s", dev.disk)
                        disk = None
                    ed.encrypted_disk = None
                    ed.save()
                provs.append(prov)
            for ed in EncryptedDisk.objects.filter(encrypted_volume=vol):
                if ed.encrypted_provider not in provs:
                    ed.delete()

    def geom_disks_dump(self, volume):
        """
        Raises:
            ValueError: UFS volume not found
        """
        provider = self.get_label_consumer('ufs', volume.vol_name)
        if provider is None:
            raise ValueError("UFS Volume %s not found" % (volume,))
        class_name = provider.xpath("../../name")[0].text

        items = []
        if class_name in ('MIRROR', 'RAID3', 'STRIPE'):
            if class_name == 'STRIPE':
                statepath = "../config/State"
                status = provider.xpath("../config/Status")[0].text
                ncomponents = int(re.search(r'Total=(?P<total>\d+)', status).group("total"))
            else:
                statepath = "./config/State"
                ncomponents = int(provider.xpath("../config/Components")[0].text)
            consumers = provider.xpath("../consumer")
            doc = self._geom_confxml()
            for consumer in consumers:
                provid = consumer.xpath("./provider/@ref")[0]
                status = consumer.xpath(statepath)[0].text
                name = doc.xpath("//provider[@id = '%s']/../name" % provid)[0].text
                items.append({
                    'type': 'dev',
                    'diskname': name,
                    'name': name,
                    'status': status,
                })
            for i in xrange(len(consumers), ncomponents):
                items.append({
                    'type': 'dev',
                    'name': 'UNAVAIL',
                    'status': 'UNAVAIL',
                })
        elif class_name == 'PART':
            name = provider.xpath("../name")[0].text
            items.append({
                'type': 'dev',
                'diskname': name,
                'name': name,
                'status': 'ONLINE',
            })
        return items

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

    def multipath_create(self, name, consumers, actives=None, mode=None):
        """
        Create an Active/Passive GEOM_MULTIPATH provider
        with name ``name`` using ``consumers`` as the consumers for it

        Modes:
            A - Active/Active
            R - Active/Read
            None - Active/Passive

        Returns:
            True in case the label succeeded and False otherwise
        """
        cmd = ["/sbin/gmultipath", "label", name] + consumers
        if mode:
            cmd.insert(2, "-%s" % (mode, ))
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        if p1.wait() != 0:
            return False
        # We need to invalidate confxml cache
        self.__confxml = None
        if p1.wait() != 0:
            return False
        return True

    def multipath_next(self):
        """
        Find out the next available name for a multipath named diskX
        where X is a crescenting value starting from 1

        Returns:
            The string of the multipath name to be created
        """
        RE_NAME = re.compile(r'[a-z]+(\d+)')
        numbers = sorted([int(RE_NAME.search(mp.name).group(1))
                        for mp in self.multipath_all() if RE_NAME.match(mp.name)
                        ])
        if not numbers:
            numbers = [0]
        for number in xrange(1, numbers[-1]+2):
            if number not in numbers:
                break
        else:
            raise ValueError('Could not find multipaths')
        return "disk%d" % number

    def _multipath_is_active(self, name, geom):
        return False

    def multipath_sync(self):
        """Synchronize multipath disks

        Every distinct GEOM_DISK that shares an ident (aka disk serial)
        is considered a multipath and will be handled by GEOM_MULTIPATH

        If the disk is not currently in use by some Volume or iSCSI Disk Extent
        then a gmultipath is automatically created and will be available for use
        """
        from freenasUI.storage.models import Volume, Disk

        doc = self._geom_confxml()

        mp_disks = []
        for geom in doc.xpath("//class[name = 'MULTIPATH']/geom"):
            for provref in geom.xpath("./consumer/provider/@ref"):
                prov = doc.xpath("//provider[@id = '%s']" % provref)[0]
                class_name = prov.xpath("../../name")[0].text
                # For now just DISK is allowed
                if class_name != 'DISK':
                    log.warn(
                        "A consumer that is not a disk (%s) is part of a "
                        "MULTIPATH, currently unsupported by middleware",
                        class_name
                    )
                    continue
                disk = prov.xpath("../name")[0].text
                mp_disks.append(disk)

        reserved = [self._find_root_dev()]

        # disks already in use count as reserved as well
        for vol in Volume.objects.all():
            reserved.extend(vol.get_disks())

        serials = defaultdict(list)
        active_active = []
        RE_CD = re.compile('^cd[0-9]')
        for geom in doc.xpath("//class[name = 'DISK']/geom"):
            name = geom.xpath("./name")[0].text
            if RE_CD.match(name) or name in reserved or name in mp_disks:
                continue
            if self._multipath_is_active(name, geom):
                active_active.append(name)
            serial = self.serial_from_device(name) or ''
            try:
                lunid = geom.xpath("./provider/config/lunid")[0].text
            except:
                lunid = ''
            serial = serial + lunid
            if not serial:
                continue
            size = geom.xpath("./provider/mediasize")[0].text
            serials[(serial, size)].append(name)

        for disks in serials.values():
            if not len(disks) > 1:
                continue
            name = self.multipath_next()
            self.multipath_create(name, disks, active_active)

        # Grab confxml again to take new multipaths into account
        doc = self._geom_confxml()
        mp_ids = []
        for geom in doc.xpath("//class[name = 'MULTIPATH']/geom"):
            _disks = []
            for provref in geom.xpath("./consumer/provider/@ref"):
                prov = doc.xpath("//provider[@id = '%s']" % provref)[0]
                class_name = prov.xpath("../../name")[0].text
                # For now just DISK is allowed
                if class_name != 'DISK':
                    continue
                disk = prov.xpath("../name")[0].text
                _disks.append(disk)
            qs = Disk.objects.filter(
                Q(disk_name__in=_disks) | Q(disk_multipath_member__in=_disks)
                )
            if qs.exists():
                diskobj = qs[0]
                mp_ids.append(diskobj.id)
                diskobj.disk_multipath_name = geom.xpath("./name")[0].text
                if diskobj.disk_name in _disks:
                    _disks.remove(diskobj.disk_name)
                if _disks:
                    diskobj.disk_multipath_member = _disks.pop()
                diskobj.save()

        Disk.objects.exclude(id__in=mp_ids).update(disk_multipath_name='', disk_multipath_member='')

    def _find_root_dev(self):
        """Find the root device.

        The original algorithm was adapted from /root/updatep*, but this
        grabs the relevant information from geom's XML facility.

        Returns:
             The root device name in string format, e.g. FreeNASp1,
             FreeNASs2, etc.

        Raises:
             AssertionError: the root device couldn't be determined.
        """

        sw_name = get_sw_name()
        doc = self._geom_confxml()

        for pref in doc.xpath("//class[name = 'LABEL']/geom/provider["
                "starts-with(name, 'ufs/%ss')]/../consumer/provider/@ref"
                % (sw_name, )):
            prov = doc.xpath("//provider[@id = '%s']" % pref)[0]
            pid = prov.xpath("../consumer/provider/@ref")[0]
            prov = doc.xpath("//provider[@id = '%s']" % pid)[0]
            name = prov.xpath("../name")[0]
            return name.text
        log.warn("Root device not found!")

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

        root_dev = self._find_root_dev()
        if root_dev and root_dev.startswith('mirror/'):
            mirror = self.gmirror_status(root_dev.split('/')[1])
            blacklist_devs = [c.get("name") for c in mirror.get("consumers")]
        else:
            blacklist_devs = [root_dev]

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

    def gmirror_status(self, name):
        """
        Get all available gmirror instances

        Returns:
            A dict describing the gmirror
        """

        doc = self._geom_confxml()
        for geom in doc.xpath("//class[name = 'MIRROR']/geom[name = '%s']" % name):
            consumers = []
            gname = geom.xpath("./name")[0].text
            status = geom.xpath("./config/State")[0].text
            for consumer in geom.xpath("./consumer"):
                ref = consumer.xpath("./provider/@ref")[0]
                prov = doc.xpath("//provider[@id = '%s']" % ref)[0]
                name = prov.xpath("./name")[0].text
                status = consumer.xpath("./config/State")[0].text
                consumers.append({
                    'name': name,
                    'status': status,
                    })
            return {
                'name': gname,
                'status': status,
                'consumers': consumers,
            }
        return None

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
        sysc = sysctl.filter(unicode(name))
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

    def __toCamelCase(self, name):
        pass1 = re.sub(r'[^a-zA-Z0-9]', ' ', name.strip())
        pass2 = re.sub(r'\s{2,}', ' ', pass1)
        camel = ''.join([word.capitalize() for word in pass2.split()])
        return camel

    def ipmi_loaded(self):
        """
        Check whether we have a valid /dev/ipmi

        Returns:
            bool: IPMI device found?
        """
        return os.path.exists('/dev/ipmi0')

    def ipmi_get_lan(self, channel=1):
        """Get lan info from ipmitool

        Returns:
            A dict object with key, val

        Raises:
            AssertionError: ipmitool lan print failed
            MiddlewareError: the ipmi device could not be found
        """

        if not self.ipmi_loaded():
            raise MiddlewareError('The ipmi device could not be found')

        RE_ATTRS = re.compile(r'^(?P<key>^.+?)\s+?:\s+?(?P<val>.+?)\r?$', re.M)

        p1 = self._pipeopen('/usr/local/bin/ipmitool lan print %d' % channel)
        ipmi = p1.communicate()[0]
        if p1.returncode != 0:
            raise AssertionError(
                "Could not retrieve data, ipmi device possibly in use?"
            )

        data = {}
        items = RE_ATTRS.findall(ipmi)
        for key, val in items:
            dkey = self.__toCamelCase(key)
            if dkey:
                data[dkey] = val.strip()
        return data

    def ipmi_set_lan(self, data, channel=1):
        """Set lan info from ipmitool

        Returns:
            0 if the operation was successful, > 0 otherwise

        Raises:
            MiddlewareError: the ipmi device could not be found
        """

        if not self.ipmi_loaded():
            raise MiddlewareError('The ipmi device could not be found')

        if data['dhcp']:
            rv = self._system_nolog(
                '/usr/local/bin/ipmitool lan set %d ipsrc dhcp' % channel
            )
        else:
            rv = self._system_nolog(
                '/usr/local/bin/ipmitool lan set %d ipsrc static' % channel
            )
            rv |= self._system_nolog(
                '/usr/local/bin/ipmitool lan set %d ipaddr %s' % (
                    channel,
                    data['ipv4address'],
                )
            )
            rv |= self._system_nolog(
                '/usr/local/bin/ipmitool lan set %d netmask %s' % (
                    channel,
                    data['ipv4netmaskbit'],
                )
            )
            rv |= self._system_nolog(
                '/usr/local/bin/ipmitool lan set %d defgw ipaddr %s' % (
                    channel,
                    data['ipv4gw'],
                )
            )

        rv |= self._system_nolog(
            '/usr/local/bin/ipmitool lan set %d access on' % channel
        )
        rv |= self._system_nolog(
            '/usr/local/bin/ipmitool lan set %d auth USER "MD2,MD5"' % channel
        )
        rv |= self._system_nolog(
            '/usr/local/bin/ipmitool lan set %d auth OPERATOR "MD2,MD5"' % (
                channel,
            )
        )
        rv |= self._system_nolog(
            '/usr/local/bin/ipmitool lan set %d auth ADMIN "MD2,MD5"' % (
                channel,
            )
        )
        rv |= self._system_nolog(
            '/usr/local/bin/ipmitool lan set %d auth CALLBACK "MD2,MD5"' % (
                channel,
            )
        )
        rv |= self._system_nolog(
            '/usr/local/bin/ipmitool lan set %d arp respond on' % channel
        )
        rv |= self._system_nolog(
            '/usr/local/bin/ipmitool lan set %d arp generate on' % channel
        )
        if data.get("ipmi_password1"):
            rv |= self._system_nolog(
                '/usr/local/bin/ipmitool user set password 2 "%s"' % (
                    pipes.quote(data.get('ipmi_password1')),
                )
            )
        rv |= self._system_nolog('/usr/local/bin/ipmitool user enable 2')
        # XXX: according to dwhite, this needs to be executed off the box via
        # the lanplus interface.
        # rv |= self._system_nolog(
        #    '/usr/local/bin/ipmitool sol set enabled true 1'
        # )
        return rv

    def _restart_system_datasets(self):
        systemdataset = self.system_dataset_create()
        if systemdataset.sys_syslog_usedataset:
            self.restart("syslogd")
        self.restart("cifs")
        if systemdataset.sys_rrd_usedataset:
            self.restart("collectd")

    def dataset_init_unix(self, dataset):
        """path = "/mnt/%s" % dataset"""
        pass

    def dataset_init_windows(self, dataset):
        acl = [
            "owner@:rwxpDdaARWcCos:fd:allow",
            "group@:rwxpDdaARWcCos:fd:allow",
            "everyone@:rxaRc:fd:allow"
        ]

        path = "/mnt/%s" % dataset
        with open("%s/.windows" % path, "w") as f:
            f.close()

        for ace in acl:
            self._pipeopen("/bin/setfacl -m '%s' '%s'" % (ace, path)).wait()

    def dataset_init_apple(self, dataset):
        path = "/mnt/%s" % dataset
        with open("%s/.apple" % path, "w") as f:
            f.close()

    def get_dataset_share_type(self, dataset):
        share_type = "unix"

        path = "/mnt/%s" % dataset
        if os.path.exists("%s/.windows" % path):
            share_type = "windows"
        elif os.path.exists("%s/.apple" % path):
            share_type = "mac"

        return share_type

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

    def system_dataset_settings(self):
        from freenasUI.storage.models import Volume
        from freenasUI.system.models import SystemDataset

        try:
            systemdataset = SystemDataset.objects.all()[0]
        except:
            systemdataset = SystemDataset.objects.create()

        # If there is a pool configured make sure the volume exists
        # Otherwise reset it to blank
        # TODO: Maybe it would be better to use a ForeignKey
        if systemdataset.sys_pool:
            volume = Volume.objects.filter(vol_name=systemdataset.sys_pool)
            if not volume.exists():
                systemdataset.sys_pool = ''
                systemdataset.save()
            else:
                volume = volume[0]

        if not systemdataset.sys_pool:
            volume = None
            for o in Volume.objects.order_by('-vol_fstype', 'vol_encrypt'):
                if o.is_decrypted():
                    volume = o
                    break
            if not volume:
                return systemdataset, None, None
            else:
                systemdataset.sys_pool = volume.vol_name
                systemdataset.save()

        basename = '%s/.system' % volume.vol_name
        return systemdataset, volume, basename

    def system_dataset_create(self):

        if (
            hasattr(self, 'failover_status') and
            self.failover_status() == 'BACKUP'
        ):
            if os.path.lexists(SYSTEMPATH):
                os.unlink(SYSTEMPATH)
            return None

        systemdataset, volume, basename = self.system_dataset_settings()
        if not volume:
            if os.path.lexists(SYSTEMPATH):
                os.unlink(SYSTEMPATH)
            return systemdataset

        datasets = [basename]
        for sub in ('samba4', 'syslog', 'cores', 'rrd'):
            datasets.append('%s/%s' % (basename, sub))

        assert volume.vol_fstype in ('ZFS', 'UFS')

        createdds = False
        for dataset in datasets:
            if volume.vol_fstype == 'ZFS':
                proc = self._pipeopen('/sbin/zfs list \'%s\'' % dataset)
                proc.communicate()
                if proc.returncode == 0:
                    continue
                self.create_zfs_dataset(dataset, _restart_collectd=False)
                createdds = True
                os.chmod('/mnt/%s' % dataset, 0755)
            else:
                if not os.path.exists(dataset):
                    try:
                        os.makedirs(dataset, mode=0755)
                    except:
                        pass

        if createdds:
            self.restart('collectd')

        corepath = '/mnt/%s/cores' % basename
        if os.path.exists(corepath):
            self._system('/sbin/sysctl kern.corefile=\'%s/%%N.core\'' % (
                corepath,
            ))
            os.chmod(corepath, 0775)

        if os.path.lexists(SYSTEMPATH):
            os.unlink(SYSTEMPATH)
        os.symlink('/mnt/%s' % basename, SYSTEMPATH)
        self.nfsv4link()

        return systemdataset

    def system_dataset_path(self):
        if not os.path.exists(SYSTEMPATH):
            return None
        return os.path.realpath(SYSTEMPATH)

    def _createlink(self, SYSTEMPATH, item):
        if not os.path.isfile(os.path.join(SYSTEMPATH, os.path.basename(item))):
            if os.path.exists(os.path.join(SYSTEMPATH, os.path.basename(item))):
                # There's something here but it's not a file.
                shutil.rmtree(os.path.join(SYSTEMPATH, os.path.basename(item)))
            open(os.path.join(SYSTEMPATH, os.path.basename(item)), "w").close()
        os.symlink(os.path.join(SYSTEMPATH, os.path.basename(item)), item)

    def nfsv4link(self):
        SYSTEMPATH = self.system_dataset_path()
        if SYSTEMPATH:
            restartfiles = ["/var/db/nfs-stablerestart", "/var/db/nfs-stablerestart.bak"]
            if (
                hasattr(self, 'failover_status') and
                self.failover_status() == 'BACKUP'
            ):
                pass
            else:
                for item in restartfiles:
                    if os.path.exists(item):
                        if os.path.isfile(item) and not os.path.islink(item):
                            # It's an honest to goodness file, this shouldn't ever happen...but
                            if not os.path.isfile(os.path.join(SYSTEMPATH, os.path.basename(item))):
                                # there's no file in the system dataset, so copy over what we have
                                # being careful to nuke anything that is there that happens to
                                # have the same name.
                                if os.path.exists(os.path.join(SYSTEMPATH, os.path.basename(item))):
                                    shutil.rmtree(os.path.join(SYSTEMPATH, os.path.basename(item)))
                                shutil.copy(item, os.path.join(SYSTEMPATH, os.path.basename(item)))
                            # Nuke the original file and create a symlink to it
                            # We don't need to worry about creating the file on the system dataset
                            # because it's either been copied over, or was already there.
                            os.unlink(item)
                            os.symlink(os.path.join(SYSTEMPATH, os.path.basename(item)), item)
                        elif os.path.isdir(item):
                            # Pathological case that should never happen
                            shutil.rmtree(item)
                            self._createlink(SYSTEMPATH, item)
                        else:
                            if not os.path.exists(os.readlink(item)):
                                # Dead symlink or some other nastiness.
                                shutil.rmtree(item)
                                self._createlink(SYSTEMPATH, item)
                    else:
                        self._createlink(SYSTEMPATH, item)

    def system_dataset_migrate(self, _from, _to):

        rsyncs = (
            ('/mnt/%s/.system/' % _from, '/mnt/%s/.system/' % _to),
        )

        restart = []
        if os.path.exists('/var/run/syslog.pid'):
            restart.append('syslogd')
            self.stop('syslogd')

        if os.path.exists('/var/run/samba/smbd.pid'):
            restart.append('cifs')
            self.stop('cifs')

        if os.path.exists('/var/run/collectd.pid'):
            restart.append('collectd')
            self.stop('collectd')

        for src, dest in rsyncs:
            rv = self._system_nolog('/usr/local/bin/rsync -az "%s" "%s"' % (
                src,
                dest,
            ))

        if _from and rv == 0:
            proc = self._pipeopen(
                '/sbin/zfs list -H -o name %s/.system|xargs zfs destroy -r' % (
                    _from,
                )
            )
            proc.communicate()

        for service in restart:
            self.start(service)

        self.nfsv4link()

    def call_backupd(self, args):
        ntries = 5
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
            backup = Backup.objects.all().order_by('-bak_started_at').first()
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
        except IOError:
            response = {'status': 'ERROR'}
        except ValueError:
            response = {'status': 'ERROR'}

        f.close()
        sock.close()
        return response

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
