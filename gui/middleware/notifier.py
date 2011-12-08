#!/usr/bin/env python
#-
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

from collections import OrderedDict
import ctypes
import glob
import grp
import os
import pwd
import re
import shlex
import shutil
import signal
import sqlite3
import stat
from subprocess import Popen, PIPE
import subprocess
import sys
import syslog
import tempfile
import time
import types

WWW_PATH = "/usr/local/www"
FREENAS_PATH = os.path.join(WWW_PATH, "freenasUI")
NEED_UPDATE_SENTINEL = '/data/need-update'
VERSION_FILE = '/etc/version'

sys.path.append(WWW_PATH)
sys.path.append(FREENAS_PATH)

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

from django.db import models

from freenasUI.common.acl import ACL_FLAGS_OS_WINDOWS, ACL_WINDOWS_FILE
from freenasUI.common.freenasacl import ACL, ACL_Hierarchy
from freenasUI.common.locks import mntlock
from freenasUI.common.pbi import pbi_add, PBI_ADD_FLAGS_NOCHECKSIG, PBI_ADD_FLAGS_INFO
from freenasUI.common.jail import Jls, Jexec
from middleware import zfs
from middleware.exceptions import MiddlewareError

class notifier:
    from os import system as ___system
    from pwd import getpwnam as ___getpwnam
    IDENTIFIER = 'notifier'
    def __system(self, command):
        syslog.openlog(self.IDENTIFIER, syslog.LOG_CONS | syslog.LOG_PID)
        syslog.syslog(syslog.LOG_NOTICE, "Executing: " + command)
        # TODO: python's signal class should be taught about sigprocmask(2)
        # This is hacky hack to work around this issue.
        libc = ctypes.cdll.LoadLibrary("libc.so.7")
        omask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        mask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        pmask = ctypes.pointer(mask)
        pomask = ctypes.pointer(omask)
        libc.sigprocmask(signal.SIGQUIT, pmask, pomask)
        try:
            self.___system("(" + command + ") 2>&1 | logger -p daemon.notice -t %s"
                           % (self.IDENTIFIER, ))
        finally:
            libc.sigprocmask(signal.SIGQUIT, pomask, None)
        syslog.syslog(syslog.LOG_INFO, "Executed: " + command)

    def __system_nolog(self, command):
        syslog.openlog(self.IDENTIFIER, syslog.LOG_CONS | syslog.LOG_PID)
        syslog.syslog(syslog.LOG_NOTICE, "Executing: " + command)
        # TODO: python's signal class should be taught about sigprocmask(2)
        # This is hacky hack to work around this issue.
        libc = ctypes.cdll.LoadLibrary("libc.so.7")
        omask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        mask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        pmask = ctypes.pointer(mask)
        pomask = ctypes.pointer(omask)
        libc.sigprocmask(signal.SIGQUIT, pmask, pomask)
        try:
            retval = self.___system("(" + command + ") >/dev/null 2>&1")
        finally:
            libc.sigprocmask(signal.SIGQUIT, pomask, None)
        syslog.syslog(syslog.LOG_INFO, "Executed: " + command)
        return retval

    def __pipeopen(self, command, log=True):
        if log:
            syslog.openlog('middleware', syslog.LOG_CONS | syslog.LOG_PID)
            syslog.syslog(syslog.LOG_NOTICE, "Popen()ing: " + command)
        return Popen(command, stdin = PIPE, stdout = PIPE, stderr = PIPE, shell = True, close_fds = True)

    def _do_nada(self):
        pass

    def _simplecmd(self, action, what):
        syslog.openlog('middleware', syslog.LOG_CONS | syslog.LOG_PID)
        syslog.syslog(syslog.LOG_DEBUG, "Calling: %s(%s) " % (action, what))
        f = getattr(self, '_' + action + '_' + what, None)
        if f is None:
            # Provide generic start/stop/restart verbs for rc.d scripts
            if action in ("start", "stop", "restart", "reload"):
                if action == 'restart':
                    self.__system("/usr/sbin/service " + what + " forcestop ")
                self.__system("/usr/sbin/service " + what + " " + action)
                f = self._do_nada
            else:
                raise ValueError("Internal error: Unknown command")
        f()

    def _started(self, what):
        service2daemon = {
            'ssh': ('sshd', '/var/run/sshd.pid'),
            'rsync': ('rsync', '/var/run/rsyncd.pid'),
            'nfs': ('nfsd', None),
            'afp': ('afpd', None),
            'cifs': ('smbd', '/var/run/samba/smbd.pid'),
            'dynamicdns': ('inadyn', None),
            'snmp': ('bsnmpd', '/var/run/snmpd.pid'),
            'ftp': ('proftpd', '/var/run/proftpd.pid'),
            'tftp': ('inetd', '/var/run/inetd.pid'),
            'iscsitarget': ('istgt', '/var/run/istgt.pid'),
            'ups': ('upsd', '/var/db/nut/upsd.pid'),
            'smartd': ('smartd', '/var/run/smartd.pid'),
        }
        """
        We need to wait a little bit so pgrep works
        My guess here is that the processes need some time to
        write the PID files before we can use them
        """
        time.sleep(0.5)
        if what in service2daemon:
            procname, pidfile = service2daemon[what]
            if pidfile:
                retval = self.__system_nolog("/bin/pgrep -F %s %s" % (pidfile, procname))
            else:
                retval = self.__system_nolog("/bin/pgrep %s" % (procname,))

            if retval == 0:
                return True
            else:
                return False
        else:
            return False

    def init(self, what, objectid = None, *args, **kwargs):
        """ Dedicated command to create "what" designated by an optional objectid.

        The helper will use method self._init_[what]() to create the object"""
        if objectid == None:
            self._simplecmd("init", what)
        else:
            f = getattr(self, '_init_' + what)
            f(objectid, *args, **kwargs)

    def destroy(self, what, objectid = None):
        if objectid == None:
            raise ValueError("Calling destroy without id")
        else:
            f = getattr(self, '_destroy_' + what)
            f(objectid)

    def start(self, what):
        """ Start the service specified by "what".

        The helper will use method self._start_[what]() to start the service.
        If the method does not exist, it would fallback using service(8)."""
        self._simplecmd("start", what)
        return self.started(what)

    def started(self, what):
        """ Test if service specified by "what" has been started. """
        try:
            f = getattr(self, '_started_' + what)
            return f()
        except:
            return self._started(what)

    def stop(self, what):
        """ Stop the service specified by "what".

        The helper will use method self._stop_[what]() to stop the service.
        If the method does not exist, it would fallback using service(8)."""
        self._simplecmd("stop", what)
        return self.started(what)

    def restart(self, what):
        """ Restart the service specified by "what".

        The helper will use method self._restart_[what]() to restart the service.
        If the method does not exist, it would fallback using service(8)."""
        self._simplecmd("restart", what)
        return self.started(what)

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

    def _restart_iscsitarget(self):
        self.__system("/usr/sbin/service ix-istgt quietstart")
        self.__system("/usr/sbin/service istgt forcestop")
        self.__system("/usr/sbin/service istgt restart")

    def _restart_collectd(self):
        self.__system("/usr/sbin/service ix-collectd quietstart")
        self.__system("/usr/sbin/service collectd restart")

    def _start_iscsitarget(self):
        self.__system("/usr/sbin/service ix-istgt quietstart")
        self.__system("/usr/sbin/service istgt restart")

    def _stop_iscsitarget(self):
        self.__system("/usr/sbin/service istgt forcestop")

    def _reload_iscsitarget(self):
        #TODO: istgt does not accept HUP yet
        #self.__system("/usr/sbin/service ix-istgt quietstart")
        #self.__system("/usr/sbin/service istgt reload")
        self._restart_iscsitarget()

    def _start_sysctl(self):
        self.__system("/usr/sbin/service ix-sysctl quietstart")
        self.__system("/usr/sbin/service sysctl start")

    def _start_network(self):
        c = self.__open_db()
        c.execute("SELECT COUNT(n.id) FROM network_interfaces n LEFT JOIN network_alias a ON a.alias_interface_id=n.id WHERE int_ipv6auto = 1 OR int_ipv6address != '' OR alias_v6address != ''")
        ipv6_interfaces = c.fetchone()[0]
        if ipv6_interfaces > 0:
            try:
                auto_linklocal = self.sysctl("net.inet6.ip6.auto_linklocal", _type='INT')
            except AssertionError:
                auto_linklocal = 0
            if auto_linklocal == 0:
                self.__system("/sbin/sysctl net.inet6.ip6.auto_linklocal=1")
                self.__system("/usr/sbin/service autolink auto_linklocal quietstart")
                self.__system("/usr/sbin/service netif stop")
        self.__system("/etc/netstart")

    def _reload_named(self):
        self.__system("/usr/sbin/service named reload")

    def _reload_networkgeneral(self):
        self.__system('/bin/hostname ""')
        self.__system("/usr/sbin/service ix-hostname quietstart")
        self.__system("/usr/sbin/service hostname quietstart")
        self.__system("/usr/sbin/service routing restart")

    def _reload_timeservices(self):
        self.__system("/usr/sbin/service ix-localtime quietstart")
        self.__system("/usr/sbin/service ix-ntpd quietstart")
        self.__system("/usr/sbin/service ntpd restart")
        c = self.__open_db()
        c.execute("SELECT stg_timezone FROM system_settings ORDER BY -id LIMIT 1")
        os.environ['TZ'] = c.fetchone()[0]
        time.tzset()

    def _reload_ssh(self):
        self.__system("/usr/sbin/service ix-sshd quietstart")
        self.__system("/usr/sbin/service sshd restart")

    def _restart_smartd(self):
        self.__system("/usr/sbin/service ix-smartd quietstart")
        self.__system("/usr/sbin/service smartd restart")

    def _restart_ssh(self):
        self.__system("/usr/sbin/service ix-sshd quietstart")
        self.__system("/usr/sbin/service sshd restart")

    def _reload_rsync(self):
        self.__system("/usr/sbin/service ix-rsyncd quietstart")
        self.__system("/usr/sbin/service rsyncd restart")

    def _restart_rsync(self):
        self.__system("/usr/sbin/service ix-rsyncd quietstart")
        self.__system("/usr/sbin/service rsyncd restart")

    def _start_ldap(self):
        self.__system("/usr/sbin/service ix-ldap quietstart")
        self.___system("(/usr/sbin/service ix-cache quietstart) &")
        self.__system("/usr/sbin/service ix-nsswitch quietstart")
        self.__system("/usr/sbin/service ix-pam quietstart")
        self.__system("/usr/sbin/service ix-samba quietstart")
        self.__system("/usr/sbin/service samba forcestop")
        self.__system("/usr/bin/killall nmbd")
        self.__system("/usr/bin/killall smbd")
        self.__system("/usr/bin/killall winbindd")
        self.__system("/bin/sleep 5")
        self.__system("/usr/sbin/service samba quietstart")

    def _started_ldap(self):
        from freenasUI.common.freenasldap import FreeNAS_LDAP, LDAPEnabled, FLAGS_DBINIT

        ret = False
        if LDAPEnabled():
            f = FreeNAS_LDAP(flags=FLAGS_DBINIT)
            f.open()
            if f.isOpen():
                ret = True
            else:
                ret = False
            f.close()

        return ret

    def _stop_ldap(self):
        self.__system("/usr/sbin/service ix-ldap quietstart")
        self.___system("(/usr/sbin/service ix-cache quietstop) &")
        self.__system("/usr/sbin/service ix-nsswitch quietstart")
        self.__system("/usr/sbin/service ix-pam quietstart")
        self.__system("/usr/sbin/service ix-samba quietstart")
        self.__system("/usr/sbin/service samba forcestop")
        self.__system("/usr/bin/killall nmbd")
        self.__system("/usr/bin/killall smbd")
        self.__system("/usr/bin/killall winbindd")
        self.__system("/bin/sleep 5")
        self.__system("/usr/sbin/service samba quietstart")

    def _restart_ldap(self):
        self._stop_ldap()
        self._start_ldap()

    def _started_activedirectory(self):
        from freenasUI.common.freenasldap import FreeNAS_ActiveDirectory, ActiveDirectoryEnabled, FLAGS_DBINIT

        for srv in ('kinit', 'activedirectory', ):
            if (self.__system_nolog('/usr/sbin/service ix-%s status' % (srv, ))
                != 0):
                return False

        ret = False
        if ActiveDirectoryEnabled():
            f = FreeNAS_ActiveDirectory(flags=FLAGS_DBINIT)
            f.open()
            if f.isOpen():
                ret = True
            else:
                ret = False
            f.close()

        return ret

    def _start_activedirectory(self):
        self.__system("/usr/sbin/service ix-kerberos quietstart")
        self.__system("/usr/sbin/service ix-nsswitch quietstart")
        self.__system("/usr/sbin/service ix-pam quietstart")
        self.__system("/usr/sbin/service ix-samba quietstart")
        self.__system("/usr/sbin/service ix-kinit quietstart")
        if self.__system_nolog('/usr/sbin/service ix-kinit status') != 0:
            # XXX: Exceptions don't work here on all versions, e.g. 8.0.2.
            #raise Exception('Failed to get a kerberos ticket.')
            return
        self.__system("/usr/sbin/service ix-activedirectory quietstart")
        if (self.__system_nolog('/usr/sbin/service ix-activedirectory status')
            != 0):
            # XXX: Exceptions don't work here on all versions, e.g. 8.0.2.
            #raise Exception('Failed to associate with the domain.')
            return
        self.___system("(/usr/sbin/service ix-cache quietstart) &")
        self.__system("/usr/sbin/service samba forcestop")
        self.__system("/usr/bin/killall nmbd")
        self.__system("/usr/bin/killall smbd")
        self.__system("/usr/bin/killall winbindd")
        self.__system("/usr/sbin/service samba quietstart")

    def _stop_activedirectory(self):
        self.__system("/usr/sbin/service ix-kerberos quietstart")
        self.__system("/usr/sbin/service ix-nsswitch quietstart")
        self.__system("/usr/sbin/service ix-pam quietstart")
        self.__system("/usr/sbin/service ix-samba quietstart")
        self.__system("/usr/sbin/service ix-kinit forcestop")
        self.__system("/usr/sbin/service ix-activedirectory forcestop")
        self.___system("(/usr/sbin/service ix-cache quietstop) &")
        self.__system("/usr/sbin/service samba forcestop")
        self.__system("/usr/bin/killall nmbd")
        self.__system("/usr/bin/killall smbd")
        self.__system("/usr/bin/killall winbindd")
        self.__system("/usr/sbin/service samba quietstart")

    def _restart_activedirectory(self):
        self._stop_activedirectory()
        self._start_activedirectory()

    def _restart_syslogd(self):
        self.__system("/usr/sbin/service ix-syslogd quietstart")
        self.__system("/usr/sbin/service syslogd restart")

    def _start_syslogd(self):
        self.__system("/usr/sbin/service ix-syslogd quietstart")
        self.__system("/usr/sbin/service syslogd start")

    def _reload_tftp(self):
        self.__system("/usr/sbin/service ix-inetd quietstart")
        self.__system("/usr/sbin/service inetd forcestop")
        self.__system("/usr/sbin/service inetd restart")

    def _restart_tftp(self):
        self.__system("/usr/sbin/service ix-inetd quietstart")
        self.__system("/usr/sbin/service inetd forcestop")
        self.__system("/usr/sbin/service inetd restart")

    def _restart_cron(self):
        self.__system("/usr/sbin/service ix-crontab quietstart")
        self.__system("/usr/sbin/service cron restart")

    def _start_motd(self):
        self.__system("/usr/sbin/service ix-motd quietstart")

    def _start_ttys(self):
        self.__system("/usr/sbin/service ix-ttys quietstart")

    def _reload_ftp(self):
        self.__system("/usr/sbin/service ix-proftpd quietstart")
        self.__system("/usr/sbin/service proftpd restart")

    def _restart_ftp(self):
        self.__system("/usr/sbin/service ix-proftpd quietstart")
        self.__system("/usr/sbin/service proftpd forcestop")
        self.__system("/usr/sbin/service proftpd restart")
        self.__system("sleep 1")

    def _start_ftp(self):
        self.__system("/usr/sbin/service ix-proftpd quietstart")
        self.__system("/usr/sbin/service proftpd start")

    def _start_ups(self):
        self.__system("/usr/sbin/service ix-ups quietstart")
        self.__system("/usr/sbin/service nut start")
        self.__system("/usr/sbin/service nut_upsmon start")
        self.__system("/usr/sbin/service nut_upslog start")

    def _stop_ups(self):
        self.__system("/usr/sbin/service nut_upslog stop")
        self.__system("/usr/sbin/service nut_upsmon stop")
        self.__system("/usr/sbin/service nut stop")

    def _restart_ups(self):
        self.__system("/usr/sbin/service ix-ups quietstart")
        self.__system("/usr/sbin/service nut restart")
        self.__system("/usr/sbin/service nut_upsmon restart")
        self.__system("/usr/sbin/service nut_upslog restart")

    def _load_afp(self):
        self.__system("/usr/sbin/service ix-afpd quietstart")
        self.__system("/usr/sbin/service dbus quietstart")
        self.__system("/usr/sbin/service avahi-daemon quietstart")
        self.__system("/usr/sbin/service netatalk quietstart")

    def _start_afp(self):
        self.__system("/usr/sbin/service ix-afpd start")
        self.__system("/usr/sbin/service dbus start")
        self.__system("/usr/sbin/service avahi-daemon start")
        self.__system("/usr/sbin/service netatalk start")

    def _stop_afp(self):
        # XXX: fix rc.d/netatalk to honor the force verbs properly.
        self.__system("killall afpd")
        self.__system("/usr/sbin/service avahi-daemon forcestop")
        self.__system("/usr/sbin/service dbus forcestop")

    def _restart_afp(self):
        self._stop_afp()
        self._start_afp()

    def _reload_afp(self):
        self.__system("/usr/sbin/service ix-afpd quietstart")
        self.__system("killall -1 afpd")

    def _reload_nfs(self):
        self.__system("/usr/sbin/service ix-nfsd quietstart")
        self.__system("/usr/sbin/service mountd reload")

    def _restart_nfs(self):
        self.__system("/usr/sbin/service lockd forcestop")
        self.__system("/usr/sbin/service statd forcestop")
        self.__system("/usr/sbin/service mountd forcestop")
        self.__system("/usr/sbin/service nfsd forcestop")
        self.__system("/usr/sbin/service ix-nfsd quietstart")
        self.__system("/usr/sbin/service mountd quietstart")
        self.__system("/usr/sbin/service nfsd quietstart")
        self.__system("/usr/sbin/service statd quietstart")
        self.__system("/usr/sbin/service lockd quietstart")

    def _start_plugins_jail(self):
        self.__system("/usr/sbin/service ix-jail quietstart")
        self.__system("/usr/sbin/service jail quietstart")
        self.__system_nolog("/usr/sbin/service ix-plugins start")

    def _stop_plugins_jail(self):
        self.__system_nolog("/usr/sbin/service ix-plugins forcestop")
        self.__system("/usr/sbin/service jail forcestop")
        self.__system("/usr/sbin/service ix-jail forcestop")

    def _restart_plugins_jail(self):
        self._stop_plugins_jail()
        self._start_plugins_jail()
    
    def _started_plugins_jail(self):
        c = self.__open_db()
        c.execute("SELECT jail_name FROM services_plugins ORDER BY -id LIMIT 1")
        jail_name = c.fetchone()[0]

        retval = 1
        idfile = "/var/run/jail_%s.id" % jail_name
        if os.access(idfile, os.F_OK):
            jail_id = int(open(idfile).read().strip())
            retval = self.__system_nolog("jls -j %d" % jail_id)

        if retval == 0:
            return True
        else:
            return False

    def _start_plugins(self, plugin=None):
        if plugin is not None:
            self.__system_nolog("/usr/sbin/service ix-plugins quietstart %s" % plugin)
        else:
            self.__system_nolog("/usr/sbin/service ix-plugins quietstart")

    def _stop_plugins(self, plugin=None):
        if plugin is not None:
            self.__system_nolog("/usr/sbin/service ix-plugins quietstop %s" % plugin)
        else:
            self.__system_nolog("/usr/sbin/service ix-plugins quietstop")

    def _restart_plugins(self, plugin=None):
        self._stop_plugins(plugin)
        self._start_plugins(plugin)

    def _started_plugins(self, plugin=None):
        res = False
        if plugin is not None:
            if self.__system_nolog("/usr/sbin/service ix-plugins status %s" % plugin) == 0:
                res = True 
        else: 
            if self.__system_nolog("/usr/sbin/service ix-plugins status") == 0:
                res = True 
        return res

    def plugins_jail_configured(self):
        res = False
        c = self.__open_db()
        c.execute("SELECT count(*) from services_plugins")
        if int(c.fetchone()[0]) > 0:
            res = True
        return res

    def _restart_dynamicdns(self):
        self.__system("/usr/sbin/service ix-inadyn quietstart")
        self.__system("/usr/sbin/service inadyn restart")

    def _restart_system(self):
        self.__system("/bin/sleep 3 && /sbin/shutdown -r now &")

    def _stop_system(self):
        self.__system("/sbin/shutdown -p now")

    def _reload_cifs(self):
        self.__system("/usr/sbin/service dbus forcestop")
        self.__system("/usr/sbin/service dbus restart")
        self.__system("/usr/sbin/service avahi-daemon forcestop")
        self.__system("/usr/sbin/service avahi-daemon restart")
        self.__system("/usr/sbin/service ix-samba quietstart")
        self.__system("/usr/sbin/service samba reload")

    def _restart_cifs(self):
        # TODO: bug in samba rc.d script
        # self.__system("/usr/sbin/service samba forcestop")
        self.__system("/usr/sbin/service dbus forcestop")
        self.__system("/usr/sbin/service dbus restart")
        self.__system("/usr/sbin/service avahi-daemon forcestop")
        self.__system("/usr/sbin/service avahi-daemon restart")
        self.__system("/usr/bin/killall nmbd")
        self.__system("/usr/bin/killall smbd")
        self.__system("/usr/sbin/service samba quietstart")

    def _restart_snmp(self):
        self.__system("/usr/sbin/service ix-bsnmpd quietstart")
        self.__system("/usr/sbin/service bsnmpd forcestop")
        self.__system("/usr/sbin/service bsnmpd quietstart")

    def _restart_http(self):
        self.__system("/usr/sbin/service ix-httpd quietstart")
        self.__system("/usr/sbin/service lighttpd restart")

    def _start_loader(self):
        self.__system("/usr/sbin/service ix-loader quietstart")

    def __saver_loaded(self):
        pipe = os.popen("kldstat|grep daemon_saver")
        out = pipe.read().strip('\n')
        pipe.close()
        return (len(out) > 0)

    def _start_saver(self):
        if not self.__saver_loaded():
            self.__system("kldload daemon_saver")

    def _stop_saver(self):
        if self.__saver_loaded():
            self.__system("kldunload daemon_saver")

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

    def __gpt_labeldisk(self, type, devname, test4k=False, swapsize=2):
        """Label the whole disk with GPT under the desired label and type"""
        if test4k:
            # Taste the disk to know whether it's 4K formatted.
            # requires > 8.1-STABLE after r213467
            ret_4kstripe = self.__system_nolog("geom disk list %s "
                                               "| grep 'Stripesize: 4096'" % (devname))
            ret_512bsector = self.__system_nolog("geom disk list %s "
                                                 "| grep 'Sectorsize: 512'" % (devname))
            # Make sure that the partition is 4k-aligned, if the disk reports 512byte sector
            # while using 4k stripe, use an offset of 64.
            need4khack = (ret_4kstripe == 0) and (ret_512bsector == 0)
        else:
            need4khack = False

        # Calculate swap size.
        swapgb = swapsize
        swapsize = swapsize * 1024 * 1024 * 2
        # Round up to nearest whole integral multiple of 128 and subtract by 34
        # so next partition starts at mutiple of 128.
        swapsize = ((swapsize+127)/128)*128
        # To be safe, wipe out the disk, both ends... before we start
        self.__system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (devname))
        try:
            p1 = self.__pipeopen("diskinfo %s" % devname)
            size = int(re.sub(r'\s+', ' ', p1.communicate()[0]).split()[2]) / (1024)
        except:
            pass
        else:
            if size*2 < swapsize:
                raise MiddlewareError('Your disk size must be higher than %dGB' % swapgb)
            # HACK: force the wipe at the end of the disk to always succeed. This
            # is a lame workaround.
            self.__system("dd if=/dev/zero of=/dev/%s bs=1m oseek=%s" % (devname, size*1024 - 4))

        commands = []
        commands.append("gpart create -s gpt /dev/%s" % (devname))
        if swapsize > 0:
            commands.append("gpart add -b 128 -t freebsd-swap -s %d %s" % (swapsize, devname))
            commands.append("gpart add -t %s %s" % (type, devname))
        else:
            commands.append("gpart add -b 128 -t %s %s" % (type, devname))

        commands.append("gpart bootcode -b /boot/pmbr-datadisk /dev/%s" % (devname))

        for command in commands:
            proc = self.__pipeopen(command)
            proc.wait()
            if proc.returncode != 0:
                raise MiddlewareError('Unable to GPT format the disk "%s"' % devname)

        # Install a dummy boot block so system gives meaningful message if booting
        # from the wrong disk.
        return need4khack

    def __gpt_unlabeldisk(self, devname):
        """Unlabel the disk"""
        swapdev = self.part_type_from_device('swap', devname)
        if swapdev != '':
            self.__system("swapoff /dev/%s" % self.part_type_from_device('swap', devname))
        self.__system("gpart destroy -F /dev/%s" % devname)

        # Wipe out the partition table by doing an additional iterate of create/destroy
        self.__system("gpart create -s gpt /dev/%s" % devname)
        self.__system("gpart destroy -F /dev/%s" % devname)

    def unlabel_disk(self, devname):
        # TODO: Check for existing GPT or MBR, swap, before blindly call __gpt_unlabeldisk
        self.__gpt_unlabeldisk(devname)

    def __prepare_zfs_vdev(self, disks, swapsize, force4khack):
        vdevs = ['']
        gnop_devs = []
        if force4khack == None:
            test4k = False
            want4khack = False
        else:
            test4k = not force4khack
            want4khack = force4khack
        first = True
        for disk in disks:
            rv = self.__gpt_labeldisk(type = "freebsd-zfs",
                                      devname = disk,
                                      test4k = (first and test4k),
                                      swapsize=swapsize)
            first = False
            if test4k:
                test4k = False
                want4khack = rv

        self.__confxml = None
        for disk in disks:

            devname = self.part_type_from_device('zfs', disk)
            if want4khack:
                self.__system("gnop create -S 4096 /dev/%s" % devname)
                devname = '/dev/%s.nop' % devname
                gnop_devs.append(devname)
            else:
                devname = "/dev/%s" % devname
            vdevs.append(devname)

        return vdevs, gnop_devs, want4khack

    def __create_zfs_volume(self, volume, swapsize, groups, force4khack=False, path=None):
        """Internal procedure to create a ZFS volume identified by volume id"""
        z_id = volume.id
        z_name = str(volume.vol_name)
        z_vdev = ""
        need4khack = False
        # Grab all disk groups' id matching the volume ID
        self.__system("swapoff -a")
        gnop_devs = []

        want4khack = force4khack

        for name, vgrp in groups.items():
            vgrp_type = vgrp['type']
            if vgrp_type != 'stripe':
                z_vdev += " " + vgrp_type
            if vgrp_type in ('cache', 'log'):
                vdev_swapsize = 0
            else:
                vdev_swapsize = swapsize
            # Prepare disks nominated in this group
            vdevs, gnops, want4khack = self.__prepare_zfs_vdev(vgrp['disks'], vdev_swapsize, want4khack)
            z_vdev += " ".join(vdevs)
            gnop_devs += gnops

        # Finally, create the zpool.
        # TODO: disallowing cachefile may cause problem if there is
        # preexisting zpool having the exact same name.
        if not os.path.isdir("/data/zfs"):
            os.makedirs("/data/zfs")

        altroot = 'none' if path else '/mnt'
        mountpoint = path if path else ('/mnt/%s' % z_name)
        p1 = self.__pipeopen("zpool create -o cachefile=/data/zfs/zpool.cache "
                      "-O aclmode=passthrough -O aclinherit=passthrough "
                      "-f -m %s -o altroot=%s %s %s" % (mountpoint, altroot, z_name, z_vdev))
        if p1.wait() != 0:
            error = ", ".join(p1.communicate()[1].split('\n'))
            raise MiddlewareError('Unable to create the pool: %s' % error)

        #We've our pool, lets retrieve the GUID
        p1 = self.__pipeopen("zpool get guid %s" % z_name)
        if p1.wait() == 0:
            line = p1.communicate()[0].split('\n')[1].strip()
            volume.vol_guid = re.sub('\s+', ' ', line).split(' ')[2]
            volume.save()
        else:
            #FIXME: warn about it?
            pass

        self.zfs_inherit_option(z_name, 'mountpoint')

        # If we have 4k hack then restore system to whatever it should be
        if want4khack:
            self.__system("zpool export %s" % (z_name))
            for gnop in gnop_devs:
                self.__system("gnop destroy %s" % gnop)
            self.__system("zpool import -R /mnt %s" % (z_name))

        self.__system("zpool set cachefile=/data/zfs/zpool.cache %s" % (z_name))

    def zfs_volume_attach_group(self, volume, group, force4khack=False):
        """Attach a disk group to a zfs volume"""
        c = self.__open_db()
        c.execute("SELECT adv_swapondrive FROM system_advanced ORDER BY -id LIMIT 1")
        swapsize=c.fetchone()[0]

        assert volume.vol_fstype == 'ZFS'
        z_name = volume.vol_name
        z_vdev = ""

        # FIXME swapoff -a is overkill
        self.__system("swapoff -a")
        vgrp_type = group['type']
        if vgrp_type != 'stripe':
            z_vdev += " " + vgrp_type

        # Prepare disks nominated in this group
        vdevs = self.__prepare_zfs_vdev(group['disks'], swapsize, force4khack)[0]
        z_vdev += " ".join(vdevs)

        # Finally, attach new groups to the zpool.
        self.__system("zpool add -f %s %s" % (z_name, z_vdev))
        self._reload_disk()

    def create_zfs_vol(self, name, size, props=None):
        """Internal procedure to create ZFS volume"""
        options = " "
        if props:
            assert type(props) is types.DictType
            for k in props.keys():
                if props[k] != 'inherit':
                    options += "-o %s=%s " % (k, props[k])
        zfsproc = self.__pipeopen("/sbin/zfs create %s -V %s %s" % (options, size, name))
        zfs_err = zfsproc.communicate()[1]
        zfs_error = zfsproc.wait()
        return zfs_error, zfs_err

    def create_zfs_dataset(self, path, props=None):
        """Internal procedure to create ZFS volume"""
        options = " "
        if props:
            assert type(props) is types.DictType
            for k in props.keys():
                if props[k] != 'inherit':
                    options += "-o %s=%s " % (k, props[k])
        zfsproc = self.__pipeopen("/sbin/zfs create %s %s" % (options, path))
        zfs_output, zfs_err = zfsproc.communicate()
        zfs_error = zfsproc.wait()
        if zfs_error == 0:
            self.restart("collectd")
        return zfs_error, zfs_err

    def list_zfs_datasets(self, path="", recursive=False):
        """Return a dictionary that contains all ZFS dataset list and their mountpoints"""
        if recursive:
            zfsproc = self.__pipeopen("/sbin/zfs list -Hr -t filesystem %s" % (path))
        else:
            zfsproc = self.__pipeopen("/sbin/zfs list -H -t filesystem %s" % (path))
        zfs_output, zfs_err = zfsproc.communicate()
        zfs_output = zfs_output.split('\n')
        zfslist = zfs.ZFSList()
        for line in zfs_output:
            if line:
                data = line.split('\t')
                # root filesystem is not treated as dataset by us
                if data[0].find('/') != -1:
                    zfslist.append(zfs.ZFSDataset(path=data[0], mountpoint=data[4]))
        return zfslist

    def list_zfs_vols(self, volname):
        """Return a dictionary that contains all ZFS volumes list"""
        zfsproc = self.__pipeopen("/sbin/zfs list -H -o name,volsize -t volume -r %s" % (str(volname),))
        zfs_output, zfs_err = zfsproc.communicate()
        zfs_output = zfs_output.split('\n')
        retval = {}
        for line in zfs_output:
            if line != "":
                data = line.split('\t')
                retval[data[0]] = {
                    'volsize': data[1],
                }
        return retval

    def list_zfs_fsvols(self):

        proc = self.__pipeopen("/sbin/zfs list -H -o name -t volume,filesystem")
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
        zfsproc = self.__pipeopen("zfs get -H freenas:state %s" % (name))
        output = zfsproc.communicate()[0]
        if output != '':
            fsname, attrname, value, source = output.split('\n')[0].split('\t')
            if value != '-' and value != 'NEW':
                return True
        return False

    def destroy_zfs_dataset(self, path, recursive=False):
        retval = None
        if '@' in path:
            MNTLOCK = mntlock()
            try:
                MNTLOCK.lock_try()
                if self.__snapshot_hold(path):
                    retval = 'Held by replication system.'
                MNTLOCK.unlock()
                del MNTLOCK
            except IOError:
                retval = 'Try again later.'
        elif recursive:
            MNTLOCK = mntlock()
            try:
                MNTLOCK.lock_try()
                zfsproc = self.__pipeopen("/sbin/zfs list -Hr -t snapshot -o name %s" % (path))
                snaps = zfsproc.communicate()[0]
                for snap in snaps.split('\n'):
                    if not snap:
                        continue
                    if self.__snapshot_hold(snap):
                        retval = '%s: Held by replication system.' % snap
                        break
                MNTLOCK.unlock()
                del MNTLOCK
            except IOError:
                retval = 'Try again later.'
        if retval == None:
            if recursive:
                zfsproc = self.__pipeopen("zfs destroy -r %s" % (path))
            else:
                zfsproc = self.__pipeopen("zfs destroy %s" % (path))
            retval = zfsproc.communicate()[1]
            if zfsproc.returncode == 0:
                from storage.models import Task, Replication
                Task.objects.filter(task_filesystem=path).delete()
                Replication.objects.filter(repl_filesystem=path).delete()
        return retval

    def destroy_zfs_vol(self, name):
        zfsproc = self.__pipeopen("zfs destroy %s" % (str(name),))
        retval = zfsproc.communicate()[1]
        return retval

    def __destroy_zfs_volume(self, volume):
        """Internal procedure to destroy a ZFS volume identified by volume id"""
        z_name = str(volume.vol_name)
        # First, destroy the zpool.
        disks = volume.get_disks()
        self.__system("zpool destroy -f %s" % (z_name))

        # Clear out disks associated with the volume
        for disk in disks:
            self.__gpt_unlabeldisk(devname = disk)

    def __create_ufs_volume(self, volume, swapsize, group):
        geom_vdev = ""
        u_name = str(volume.vol_name)
        # TODO: We do not support multiple GEOM levels for now.
        geom_type = group['type']

        if geom_type == '':
            # Grab disk from the group
            disk = group['disks'][0]
            self.__gpt_labeldisk(type = "freebsd-ufs", devname = disk, swapsize=swapsize)
            devname = self.part_type_from_device('ufs', disk)
            # TODO: Need to investigate why /dev/gpt/foo can't have label /dev/ufs/bar
            # generated automatically
            p1 = self.__pipeopen("newfs -U -L %s /dev/%s" % (u_name, devname))
            stderr = p1.communicate()[1]
            if p1.returncode != 0:
                error = ", ".join(stderr.split('\n'))
                raise MiddlewareError('Volume creation failed: "%s"' % error)
        else:
            # Grab all disks from the group
            for disk in group['disks']:
                # FIXME: turn into a function
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (disk,))
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m oseek=`diskinfo %s "
                      "| awk '{print int($3 / (1024*1024)) - 4;}'`" % (disk, disk))
                geom_vdev += " /dev/" + disk
                #TODO gpt label disks
            self.__system("geom %s load" % (geom_type))
            p1 = self.__pipeopen("geom %s label %s %s" % (geom_type, volume.vol_name, geom_vdev))
            stdout, stderr = p1.communicate()
            if p1.returncode != 0:
                error = ", ".join(stderr.split('\n'))
                raise MiddlewareError('Volume creation failed: "%s"' % error)
            ufs_device = "/dev/%s/%s" % (geom_type, volume.vol_name)
            self.__system("newfs -U -L %s %s" % (u_name, ufs_device))

    def __destroy_ufs_volume(self, volume):
        """Internal procedure to destroy a UFS volume identified by volume id"""
        u_name = str(volume.vol_name)

        disks = volume.get_disks()
        provider = self.get_label_provider('ufs', u_name)
        geom_type = provider.xpathEval("../../name")[0].content.lower()

        if geom_type not in ('mirror', 'stripe', 'raid3'):
            # Grab disk from the group
            disk = disks[0]
            self.__system("umount -f /dev/ufs/" + u_name)
            self.__gpt_unlabeldisk(devname = disk)
        else:
            g_name = provider.xpathEval("../name")[0].content
            self.__system("swapoff -a")
            self.__system("umount -f /dev/ufs/" + u_name)
            self.__system("geom %s stop %s" % (geom_type, g_name))
            # Grab all disks from the group
            for disk in disks:
                self.__system("geom %s clear %s" % (geom_type, disk))
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (disk,))
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m oseek=`diskinfo %s "
                      "| awk '{print int($3 / (1024*1024)) - 4;}'`" % (disk, disk))

    def _init_volume(self, volume, *args, **kwargs):
        """Initialize a volume designated by volume_id"""
        c = self.__open_db()
        c.execute("SELECT adv_swapondrive FROM system_advanced ORDER BY -id LIMIT 1")
        swapsize=c.fetchone()[0]
        c.close()

        assert volume.vol_fstype == 'ZFS' or volume.vol_fstype == 'UFS'
        if volume.vol_fstype == 'ZFS':
            self.__create_zfs_volume(volume, swapsize, kwargs.pop('groups', False), kwargs.pop('force4khack', False), kwargs.pop('path', None))
        elif volume.vol_fstype == 'UFS':
            self.__create_ufs_volume(volume, swapsize, kwargs.pop('groups')['root'])

    def zfs_replace_disk(self, volume, from_label, to_disk):
        """Replace disk in zfs called `from_label` to `to_disk`"""
        c = self.__open_db()
        c.execute("SELECT adv_swapondrive FROM system_advanced ORDER BY -id LIMIT 1")
        swapsize = c.fetchone()[0]

        assert volume.vol_fstype == 'ZFS'

        # TODO: Test on real hardware to see if ashift would persist across replace
        from_disk = self.label_to_disk(from_label)
        from_swap = self.part_type_from_device('swap', from_disk)

        if from_swap != '':
            self.__system('/sbin/swapoff /dev/%s' % (from_swap))

        # to_disk _might_ have swap on, offline it before gpt label
        to_swap = self.part_type_from_device('swap', to_disk)
        if to_swap != '':
            self.__system('/sbin/swapoff /dev/%s' % (to_swap))

        # Replace in-place
        if from_disk == to_disk:
            self.__system('/sbin/zpool offline %s %s' % (volume.vol_name, from_label))

        self.__gpt_labeldisk(type = "freebsd-zfs", devname = to_disk, swapsize=swapsize)

        # invalidate cache
        self.__confxml = None
        # There might be a swap after __gpt_labeldisk
        to_swap = self.part_type_from_device('swap', to_disk)
        # It has to be a freebsd-zfs partition there
        to_label = self.part_type_from_device('zfs', to_disk)
        if to_label == '':
            raise MiddlewareError('freebsd-zfs partition could not be found')

        if to_swap != '':
            self.__system('/sbin/swapon /dev/%s' % (to_swap))

        if from_disk == to_disk:
            self.__system('/sbin/zpool online %s %s' % (volume.vol_name, to_label))
            ret = self.__system_nolog('/sbin/zpool replace %s %s' % (volume.vol_name, to_label))
            if ret == 256:
                ret = self.__system_nolog('/sbin/zpool scrub %s' % (volume.vol_name))
        else:
            p1 = self.__pipeopen('/sbin/zpool replace %s %s %s' % (volume.vol_name, from_label, to_label))
            stdout, stderr = p1.communicate()
            ret = p1.returncode
            if ret != 0:
                if from_swap != '':
                    self.__system('/sbin/swapon /dev/%s' % (from_swap))
                error = ", ".join(stderr.split('\n'))
                if to_swap != '':
                    self.__system('/sbin/swapoff /dev/%s' % (to_swap))
                raise MiddlewareError('Disk replacement failed: "%s"' % error)

        if to_swap:
            self.__system('/sbin/swapon /dev/%s' % (to_swap))

        return ret

    def zfs_offline_disk(self, volume, label):

        assert volume.vol_fstype == 'ZFS'

        # TODO: Test on real hardware to see if ashift would persist across replace
        disk = self.label_to_disk(label)
        swap = self.part_type_from_device('swap', disk)

        if swap != '':
            self.__system('/sbin/swapoff /dev/%s' % (swap))

        # Replace in-place
        p1 = self.__pipeopen('/sbin/zpool offline %s %s' % (volume.vol_name, label))
        stderr = p1.communicate()[1]
        if p1.returncode != 0:
            error = ", ".join(stderr.split('\n'))
            raise MiddlewareError('Disk replacement failed: "%s"' % error)

    def zfs_detach_disk(self, volume, label):
        """Detach a disk from zpool
           (more technically speaking, a replaced disk.  The replacement actually
           creates a mirror for the device to be replaced)"""

        assert volume.vol_fstype == 'ZFS'

        from_disk = self.label_to_disk(label)
        from_swap = self.part_type_from_device('swap', from_disk)

        # Remove the swap partition for another time to be sure.
        # TODO: swap partition should be trashed instead.
        if from_swap != '':
            self.__system('/sbin/swapoff /dev/%s' % (from_swap,))

        ret = self.__system_nolog('/sbin/zpool detach %s %s' % (volume.vol_name, label))
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
            self.__system('/sbin/swapoff /dev/%s' % (from_swap,))

        p1 = self.__pipeopen('/sbin/zpool remove %s %s' % (volume.vol_name, label))
        stderr = p1.communicate()[1]
        if p1.returncode != 0:
            error = ", ".join(stderr.split('\n'))
            raise MiddlewareError('Disk could not be removed: "%s"' % error)
        # TODO: This operation will cause damage to disk data which should be limited

        self.__gpt_unlabeldisk(from_disk)

    def detach_volume_swaps(self, volume):
        """Detach all swaps associated with volume"""
        disks = volume.get_disks()
        for disk in disks:
            swapdev = self.part_type_from_device('swap', disk)
            if swapdev != '':
                self.__system("swapoff /dev/%s" % swapdev)

    def _destroy_volume(self, volume):
        """Destroy a volume designated by volume_id"""

        assert volume.vol_fstype in ('ZFS', 'UFS', 'iscsi', 'NTFS', 'MSDOSFS', 'EXT2FS')
        if volume.vol_fstype == 'ZFS':
            self.__destroy_zfs_volume(volume)
        elif volume.vol_fstype == 'UFS':
            self.__destroy_ufs_volume(volume)
        self._reload_disk()

    def _reload_disk(self):
        self.__system("/usr/sbin/service ix-fstab quietstart")
        self.__system("/usr/sbin/service swap1 quietstart")
        self.__system("/usr/sbin/service mountlate quietstart")
        self.restart("collectd")
        self.__confxml = None

    # Create a user in system then samba
    def __pw_with_password(self, command, password):
        pw = self.__pipeopen(command)
        msg = pw.communicate("%s\n" % password)[1]
        if pw.returncode != 0:
            raise MiddlewareError("Operation could not be performed. %s" % msg)

        if msg != "":
            syslog.syslog(syslog.LOG_NOTICE, "Command reports " + msg)

    def __smbpasswd(self, username, password):
        command = '/usr/local/bin/smbpasswd -s -a "%s"' % (username)
        smbpasswd = self.__pipeopen(command)
        smbpasswd.communicate("%s\n%s\n" % (password, password))

    def __issue_pwdchange(self, username, command, password):
        self.__pw_with_password(command, password)
        self.__smbpasswd(username, password)

    def user_create(self, username, fullname, password, uid = -1, gid = -1,
                    shell = "/sbin/nologin", homedir = "/mnt", password_disabled = False,
                    locked = False):
        """Creates a user with the given parameters.
        uid and gid can be omitted or specified as -1 which means the system should
        choose automatically.

        The default shell is /sbin/nologin.

        Returns user uid and gid"""
        if password_disabled:
            command = '/usr/sbin/pw useradd "%s" -h - -c "%s"' % (username, fullname)
        else:
            command = '/usr/sbin/pw useradd "%s" -h 0 -c "%s"' % (username, fullname)
        if uid >= 0:
            command += " -u %d" % (uid)
        if gid >= 0:
            command += " -g %d" % (gid)
        if homedir != '/nonexistent':
            command += ' -s "%s" -d "%s" -m' % (shell, homedir)
        else:
            command += ' -s "%s" -d "%s"' % (shell, homedir)
        self.__issue_pwdchange(username, command, password)
        if locked:
            self.user_lock(username)
        if password_disabled:
            smb_hash = ""
        else:
            smb_command = "/usr/local/bin/pdbedit -w %s" % username
            smb_cmd = self.__pipeopen(smb_command)
            smb_hash = smb_cmd.communicate()[0].split('\n')[0]
        user = self.___getpwnam(username)
        return (user.pw_uid, user.pw_gid, user.pw_passwd, smb_hash)

    def user_lock(self, username):
        self.__system('/usr/local/bin/smbpasswd -d "%s"' % (username))
        self.__system('/usr/sbin/pw lock "%s"' % (username))
        return self.user_gethashedpassword(username)

    def user_unlock(self, username):
        self.__system('/usr/local/bin/smbpasswd -e "%s"' % (username))
        self.__system('/usr/sbin/pw unlock "%s"' % (username))
        return self.user_gethashedpassword(username)

    def user_changepassword(self, username, password):
        """Changes user password"""
        command = '/usr/sbin/pw usermod "%s" -h 0' % (username)
        self.__issue_pwdchange(username, command, password)
        return self.user_gethashedpassword(username)

    def user_gethashedpassword(self, username):
        smb_command = "/usr/local/bin/pdbedit -w %s" % username
        smb_cmd = self.__pipeopen(smb_command)
        smb_hash = smb_cmd.communicate()[0].split('\n')[0]
        user = self.___getpwnam(username)
        return (user.pw_passwd, smb_hash)

    def user_deleteuser(self, username):
        self.__system('/usr/sbin/pw userdel "%s"' % (username))

    def user_deletegroup(self, groupname):
        self.__system('/usr/sbin/pw groupdel "%s"' % (groupname))

    def user_getnextuid(self):
        command = "/usr/sbin/pw usernext"
        pw = self.__pipeopen(command)
        uidgid = pw.communicate()
        uid = uidgid[0].split(':')[0]
        return uid

    def user_getnextgid(self):
        command = "/usr/sbin/pw groupnext"
        pw = self.__pipeopen(command)
        uidgid = pw.communicate()
        gid = uidgid[0]
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
            self.__system("/sbin/mount -uw /")
        saved_umask = os.umask(077)
        if not os.path.isdir(sshpath):
            os.makedirs(sshpath)
        if not os.path.isdir(sshpath):
            return # FIXME: need better error reporting here
        if pubkey == '' and os.path.exists(keypath):
            os.unlink(keypath)
        else:
            fd = open(keypath, 'w')
            fd.write(pubkey)
            fd.close()
            self.__system("/usr/sbin/chown -R %s:%s %s" % (username, groupname, sshpath))
        if homedir == '/root':
            self.__system("/sbin/mount -u /")
        os.umask(saved_umask)

    def _reload_user(self):
        self.__system("/usr/sbin/service ix-passwd quietstart")
        self.__system("/usr/sbin/service ix-aliases quietstart")
        self.reload("cifs")

    def mp_change_permission(self, path='/mnt', user='root', group='wheel',
                             mode='0755', recursive=False, acl='unix'):

        winacl = os.path.join(path, ACL_WINDOWS_FILE)
        winexists = (ACL.get_acl_ostype(path) == ACL_FLAGS_OS_WINDOWS)
        if acl == 'windows' and not winexists:
            open(winacl, 'a').close()
        elif acl == 'unix' and winexists:
            os.unlink(winacl)

        hier = ACL_Hierarchy(path)
        hier.set_defaults(recursive=recursive)
        hier.chown(user + ":" + group, recursive)
        hier.chmod(mode, recursive)
        hier.close()

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

    def change_upload_location(self, path, pbi=False):
        dir = "pbi" if pbi is True else "firmware"
        vardir = "/var/tmp/%s" % dir

        self.__system("/bin/rm -rf %s" % vardir)
        self.__system("/bin/mkdir -p %s/.freenas" % path)
        self.__system("/usr/sbin/chown www:www %s/.freenas" % path)
        self.__system("/bin/ln -s %s/.freenas %s" % (path, vardir))

    def validate_xz(self, path):
        ret = self.__system_nolog("/usr/bin/xz -t %s" % (path))
        if ret == 0:
            return True
        return False

    def update_firmware(self, path):
        syslog.openlog('updater', syslog.LOG_CONS | syslog.LOG_PID)
        try:
            cmd1 = '/usr/bin/xzcat %s' % (path, )
            cmd2 = 'sh -x /root/update'
            syslog.syslog(syslog.LOG_NOTICE,
                          'Executing: %s | %s' % (cmd1, cmd2, ))
            p1 = subprocess.Popen(shlex.split(cmd1), stdout=subprocess.PIPE)
            output = subprocess.check_output(shlex.split(cmd2),
                                             stdin=p1.stdout,
                                             stderr=subprocess.PIPE)
        except subprocess.CalledProcessError, cpe:
            raise MiddlewareError('The update failed: %s' % (str(cpe), ))
        finally:
            os.unlink(path)
            syslog.closelog()
        open(NEED_UPDATE_SENTINEL, 'w').close()

    def apply_servicepack(self):
        self.__system("/usr/bin/xz -cd /var/tmp/firmware/servicepack.txz | /usr/bin/tar xf - -C /var/tmp/firmware/ etc/servicepack/version.expected")
        try:
            with open(VERSION_FILE) as f:
                freenas_build = f.read()
        except:
            raise MiddlewareError('Could not determine software version from '
                                  'running system')
        try:
            with open('/var/tmp/firmware/etc/servicepack/version.expected') as f:
                expected_build = f.read()
        except:
            raise MiddlewareError('Could not determine software version from '
                                  'service pack')
        if freenas_build != expected_build:
            raise MiddlewareError('Software versions did not match ("%s" != '
                                  '"%s")' % (freenas_build, expected_build))
        self.__system("/sbin/mount -uw /")
        self.__system("/usr/bin/xz -cd /var/tmp/firmware/servicepack.txz | /usr/bin/tar xf - -C /")
        self.__system("/bin/sh /etc/servicepack/post-install")
        self.__system("/bin/rm -fr /var/tmp/firmware/servicepack.txz")
        self.__system("/bin/rm -fr /var/tmp/firmware/etc")


    def install_pbi(self):
        ret = False

        if self._started_plugins():
            (c, conn) = self.__open_db(ret_conn=True)
            c.execute("SELECT jail_name FROM services_plugins ORDER BY -id LIMIT 1")
            jail_name = c.fetchone()[0]

            c.execute("SELECT plugins_path FROM services_plugins ORDER BY -id LIMIT 1")
            plugins_path = c.fetchone()[0]

            jail = None
            for j in Jls():
                if j.hostname == jail_name:
                    jail = j 
                    break

            # this stuff needs better error checking.. .. ..
            if jail is not None:
                pbi = prefix = name = version = None

                p = pbi_add(flags=PBI_ADD_FLAGS_INFO, pbi="/mnt/.freenas/pbifile.pbi")
                out = p.info(True, j.jid, 'pbi information for', 'prefix', 'name', 'version')
                for pair in out:
                    (var, val) = pair.split('=')

                    var = var.lower()
                    if var == 'pbi information for':
                        pbi = "%s.pbi" % val

                    elif var == 'prefix':
                        prefix = val

                    elif var == 'name':
                        name = val

                    elif var == 'version':
                        version = val

                self.__system("/bin/mv /var/tmp/pbi/pbifile.pbi %s/%s" % (plugins_path, pbi))

                p = pbi_add(flags=PBI_ADD_FLAGS_NOCHECKSIG, pbi="/mnt/%s" % pbi)
                res = p.run(jail=True, jid=j.jid)
                if res and res[0] == 0:

                    kwargs = {}
                    kwargs['path'] = prefix
                    kwargs['enabled'] = False
                    kwargs['ip'] = jail.ip

                    # icky, icky icky, this is how we roll though.
                    port = 12345
                    c.execute("SELECT count(*) FROM plugins_plugins")
                    count = c.fetchone()[0]
                    if count > 0: 
                        c.execute("SELECT plugin_port FROM plugins_plugins ORDER BY plugin_port DESC LIMIT 1")
                        port = int(c.fetchone()[0])

                    kwargs['port'] = port + 1

                    out = Jexec(jid=j.jid, command="cat %s/freenas" % prefix).run()
                    if out and out[0] == 0:
                        out = out[1]
                        for line in out.splitlines():
                            parts = line.split(':')
                            key = parts[0].strip().lower()
                            if key in ('uname', 'name', 'icon'):
                                kwargs[key] = parts[1].strip()
                                if key == 'name':
                                    kwargs['view'] = "/plugins/%s/%s" % (name, version)

                    sqlvars = ""
                    sqlvals = ""
                    for key in kwargs:
                        sqlvars += "plugin_%s," % key
                        sqlvals += ":%s," % key

                    sqlvars = sqlvars.rstrip(',')
                    sqlvals = sqlvals.rstrip(',')

                    sql = "INSERT INTO plugins_plugins(%s) VALUES(%s)" % (sqlvars, sqlvals)
                    syslog.syslog(syslog.LOG_INFO, "install_pbi: sql = %s" % sql)
                    try:
                        c.execute(sql, kwargs)
                        conn.commit()
                        ret = True

                    except:
                        ret = False                     
        return ret


    def get_volume_status(self, name, fs):
        status = 'UNKNOWN'
        if fs == 'ZFS':
            p1 = self.__pipeopen('zpool list -H -o health %s' % str(name), log=False)
            if p1.wait() == 0:
                status = p1.communicate()[0].strip('\n')
        elif fs == 'UFS':

            provider = self.get_label_provider('ufs', name)
            gtype = provider.xpathEval("../../name")[0].content

            if gtype in ('MIRROR', 'STRIPE', 'RAID3'):

                search = provider.xpathEval("../config/State")
                if len(search) > 0:
                    status = search[0].content

            else:
                p1 = self.__pipeopen('mount|grep "/dev/ufs/%s"' % name)
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
            'sha256' : '/sbin/sha256 -q',
        }
        hasher = self.__pipeopen('%s %s' % (algorithm2map[algorithm], path))
        sum = hasher.communicate()[0].split('\n')[0]
        return sum

    def get_disks(self):

        disksd = {}

        for disk in self.__get_disks():
            info = self.__pipeopen('/usr/sbin/diskinfo %s' % disk).communicate()[0].split('\t')
            if len(info) > 3:
                disksd.update({
                    disk: {
                        'devname': info[0],
                        'capacity': info[2]
                    },
                })

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
                        'devname': os.path.basename(info[0]),
                        'capacity': info[2]
                    },
                })
        return partitions

    def precheck_partition(self, dev, fstype):

        if fstype == 'UFS':
            p1 = self.__pipeopen("/sbin/fsck_ufs -p %s" % dev)
            p1.communicate()
            if p1.returncode == 0:
                return True
        elif fstype == 'NTFS':
            return True
        elif fstype == 'MSDOSFS':
            p1 = self.__pipeopen("/sbin/fsck_msdosfs -p %s" % dev)
            p1.communicate()
            if p1.returncode == 0:
                return True
        elif fstype == 'EXT2FS':
            p1 = self.__pipeopen("/sbin/fsck_ext2fs -p %s" % dev)
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
            return False
        if p1.wait() == 0:
            return True
        return False

    def detect_volumes(self, extra=None):
        """
        Responsible to detect existing volumes by running
        g{mirror,stripe,raid3},zpool commands

        Used by: Automatic Volume Import
        """

        volumes = []
        doc = self.__geom_confxml()
        # Detect GEOM mirror, stripe and raid3
        for geom in ('mirror', 'stripe', 'raid3'):
            search = doc.xpathEval("//class[name = '%s']/geom/config" % (geom.upper(),))
            for entry in search:
                label = entry.xpathEval('../name')[0].content
                disks = []
                for consumer in entry.xpathEval('../consumer/provider'):
                    provider = consumer.prop("ref")
                    device = doc.xpathEval("//class[name = 'DISK']//provider[@id = '%s']/name" % provider)
                    disks.append( {'name': device[0].content} )

                # Next thing is find out whether this is a raw block device or has GPT
                #TODO: MBR?
                search = doc.xpathEval("//class[name = 'PART']/geom[name = '%s/%s']/provider//config[type = 'freebsd-ufs']" % (geom,label))
                if len(search) > 0:
                    label = search[0].xpathEval("../name")[0].content.split('/', 1)[1]
                volumes.append({
                    'label': label,
                    'type': 'geom',
                    'group_type': geom,
                    'disks': {'vdevs': [{'disks': disks, 'name': geom}]},
                    })

        RE_POOL_NAME = re.compile(r'pool: (?P<name>[a-z][a-z0-9_-]+)', re.I)
        p1 = self.__pipeopen("zpool import")
        res = p1.communicate()[0]

        for pool in RE_POOL_NAME.findall(res):
            # get status part of the pool
            status = res.split('pool: %s\n' % pool)[1].split('pool:')[0]
            roots = zfs.parse_status(pool, doc, status)

            if roots[pool].status != 'UNAVAIL':
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

    def zfs_import(self, name, id):
        imp = self.__pipeopen('zpool import -R /mnt %s' % id)
        stdout, stderr = imp.communicate()
        if imp.returncode == 0:
            # Reset all mountpoints in the zpool
            self.zfs_inherit_option(name, 'mountpoint', True)
            # Remember the pool cache
            self.__system("zpool set cachefile=/data/zfs/zpool.cache %s" % (name))
            # These should probably be options that are configurable from the GUI
            self.__system("zfs set aclmode=passthrough %s" % name)
            self.__system("zfs set aclinherit=passthrough %s" % name)
            return True
        return False

    def zfs_export(self, name):
        imp = self.__pipeopen('zpool export %s' % str(name))
        stdout, stderr = imp.communicate()
        if imp.returncode != 0:
            raise MiddlewareError('Unable to export %s: %s' % (name, stderr))
        return True

    def volume_export(self, vol):
        if vol.vol_fstype == 'ZFS':
            self.zfs_export(vol.vol_name)
        else:
            p1 = self.__pipeopen("umount /mnt/%s" % vol.vol_name)
            if p1.wait() != 0:
                return False
        return True

    def zfs_scrub(self, name, stop=False):
        if stop:
            imp = self.__pipeopen('zpool scrub -s %s' % str(name))
        else:
            imp = self.__pipeopen('zpool scrub %s' % str(name))
        stdout, stderr = imp.communicate()
        if imp.returncode != 0:
            raise MiddlewareError('Unable to scrub %s: %s' % (name, stderr))
        return True

    def zfs_snapshot_list(self, path=None):
        fsinfo = dict()

        zfsproc = self.__pipeopen("/sbin/zfs list -t volume -o name -H")
        zvols = filter(lambda y: y != '', zfsproc.communicate()[0].split('\n'))

        if path:
            zfsproc = self.__pipeopen("/sbin/zfs list -r -t snapshot -H -S creation %s" % path)
        else:
            zfsproc = self.__pipeopen("/sbin/zfs list -t snapshot -H -S creation")
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
                snaplist.insert(0, dict([('fullname', snapname), ('name', name), ('used', used), ('refer', refer), ('mostrecent', mostrecent), ('parent', 'filesystem' if fs not in zvols else 'volume')]))
                fsinfo[fs] = snaplist
        return fsinfo

    def zfs_mksnap(self, path, name, recursive):
        if recursive:
            p1 = self.__pipeopen("/sbin/zfs snapshot -r %s@%s" % (path, name))
        else:
            p1 = self.__pipeopen("/sbin/zfs snapshot %s@%s" % (path, name))
        if p1.wait() != 0:
            err = p1.communicate()[1]
            raise MiddlewareError("Snapshot could not be taken: %s" % err)
        return True

    def zfs_clonesnap(self, snapshot, dataset):
        zfsproc = self.__pipeopen('zfs clone %s %s' % (snapshot, dataset))
        retval = zfsproc.communicate()[1]
        return retval

    def rollback_zfs_snapshot(self, snapshot):
        zfsproc = self.__pipeopen('zfs rollback %s' % (snapshot))
        retval = zfsproc.communicate()[1]
        return retval

    def config_restore(self):
        os.unlink("/data/freenas-v1.db")
        save_path = os.getcwd()
        os.chdir(FREENAS_PATH)
        self.__system("/usr/local/bin/python manage.py syncdb --noinput --migrate")
        self.__system("/usr/local/bin/python manage.py createadmin")
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

    def zfs_get_options(self, name):
        data = {}
        noinherit_fields = ['quota', 'refquota', 'reservation', 'refreservation']
        zfsname = str(name)

        zfsproc = self.__pipeopen("/sbin/zfs get -H -o property,value,source all %s" % (zfsname))
        zfs_output = zfsproc.communicate()[0]
        zfs_output = zfs_output.split('\n')
        retval = {}
        for line in zfs_output:
            if line != "":
                data = line.split('\t')
                if (not data[0] in noinherit_fields) and (data[2] == 'default' or data[2].startswith('inherited')):
                    retval[data[0]] = "inherit"
                else:
                    retval[data[0]] = data[1]
        return retval

    def zfs_set_option(self, name, item, value):
        name = str(name)
        item = str(item)
        value = str(value)
        zfsproc = self.__pipeopen('zfs set %s=%s "%s"' % (item, value, name))
        zfsproc.wait()
        if zfsproc.returncode == 0:
            return True
        return False

    def zfs_inherit_option(self, name, item, recursive=False):
        name = str(name)
        item = str(item)
        if recursive:
            zfscmd = 'zfs inherit -r %s %s' % (item, name)
        else:
            zfscmd = 'zfs inherit %s %s' % (item, name)
        zfsproc = self.__pipeopen(zfscmd)
        zfsproc.wait()
        return (zfsproc.returncode == 0)

    def zfs_dataset_release_snapshots(self, name, recursive=False):
        name = str(name)
        retval = None
        if recursive:
            zfscmd = "/sbin/zfs list -Ht snapshot -o name,freenas:state -r %s" % (name)
        else:
            zfscmd = "/sbin/zfs list -Ht snapshot -o name,freenas:state -r -d 1 %s" % (name)
        MNTLOCK = mntlock()
        try:
            MNTLOCK.lock_try()
            zfsproc = self.__pipeopen(zfscmd)
            output = zfsproc.communicate()[0]
            if output != '':
                snapshots_list = output.split('\n')
            for snapshot_item in snapshots_list:
                if snapshot_item != '':
                    snapshot, state = snapshot_item.split('\t')
                    if state != '-':
                        self.zfs_inherit_option(snapshot, 'freenas:state')
            MNTLOCK.unlock()
            del MNTLOCK
        except IOError:
            retval = 'Try again later.'
        return retval

    # Reactivate replication on all snapshots
    def zfs_dataset_reset_replicated_snapshots(self, name, recursive=False):
        name = str(name)
        retval = None
        if recursive:
            zfscmd = "/sbin/zfs list -Ht snapshot -o name,freenas:state -r %s" % (name)
        else:
            zfscmd = "/sbin/zfs list -Ht snapshot -o name,freenas:state -r -d 1 %s" % (name)
        MNTLOCK = mntlock()
        try:
            MNTLOCK.lock_try()
            zfsproc = self.__pipeopen(zfscmd)
            output = zfsproc.communicate()[0]
            if output != '':
                snapshots_list = output.split('\n')
            for snapshot_item in snapshots_list:
                if snapshot_item != '':
                    snapshot, state = snapshot_item.split('\t')
                    if state != 'NEW':
                        self.zfs_set_option(snapshot, 'freenas:state', 'NEW')
            MNTLOCK.unlock()
            del MNTLOCK
        except IOError:
            retval = 'Try again later.'
        return retval

    def geom_disk_replace(self, volume, to_disk):
        """Replace disk in volume_id from from_diskid to to_diskid"""
        """Gather information"""

        assert volume.vol_fstype == 'UFS'

        provider = self.get_label_provider('ufs', volume.vol_name)
        class_name = provider.xpathEval("../../name")[0].content
        geom_name = provider.xpathEval("../name")[0].content

        if class_name == "MIRROR":
            rv = self.__system_nolog("geom mirror forget %s" % (geom_name,))
            if rv != 0:
                return rv
            p1 = self.__pipeopen("geom mirror insert %s /dev/%s" % (str(geom_name), str(to_disk),))
            stdout, stderr = p1.communicate()
            if p1.returncode != 0:
                error = ", ".join(stderr.split('\n'))
                raise MiddlewareError('Replacement failed: "%s"' % error)
            return 0

        elif class_name == "RAID3":
            numbers = provider.xpathEval("../consumer/config/Number")
            ncomponents =int( provider.xpathEval("../config/Components")[0].content)
            numbers = [int(node.content) for node in numbers]
            lacking = [x for x in xrange(ncomponents) if x not in numbers][0]
            p1 = self.__pipeopen("geom raid3 insert -n %d %s %s" % \
                                        (lacking, str(geom_name), str(to_disk),))
            stdout, stderr = p1.communicate()
            if p1.returncode != 0:
                error = ", ".join(stderr.split('\n'))
                raise MiddlewareError('Replacement failed: "%s"' % error)
            return 0

        return 1

    def iface_destroy(self, name):
        self.__system("ifconfig %s destroy" % name)

    def __init__(self):
        self.__confxml = None
        self.__diskserial = {}

    def __geom_confxml(self):
        if self.__confxml == None:
            from libxml2 import parseDoc
            self.__confxml = parseDoc(self.sysctl('kern.geom.confxml'))
        return self.__confxml

    def serial_from_device(self, devname):
        if devname in self.__diskserial:
            return self.__diskserial.get(devname)
        p1 = Popen(["/usr/local/sbin/smartctl", "-i", "/dev/%s" % devname], stdout=PIPE)
        output = p1.communicate()[0]
        search = re.search(r'^Serial Number:[ \t\s]+(?P<serial>.+)', output, re.I|re.M)
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
        doc = self.__geom_confxml()

        # try to find the provider from GEOM_LABEL
        search = doc.xpathEval("//class[name = 'LABEL']//provider[name = '%s']/../consumer/provider/@ref" % name)
        if len(search) > 0:
            provider = search[0].content
        else:
            # the label does not exist, try to find it in GEOM DEV
            search = doc.xpathEval("//class[name = 'DEV']/geom[name = '%s']//provider/@ref" % name)
            if len(search) > 0:
                provider = search[0].content
            else:
                return None
        search = doc.xpathEval("//provider[@id = '%s']/../name" % provider)
        disk = search[0].content
        return disk

    def device_to_identifier(self, name):
        name = str(name)
        doc = self.__geom_confxml()

        serial = self.serial_from_device(name)
        if serial:
            return "{serial}%s" % serial

        search = doc.xpathEval("//class[name = 'PART']/..//*[name = '%s']//config[type = 'freebsd-zfs']/rawuuid" % name)
        if len(search) > 0:
            return "{uuid}%s" % search[0].content
        search = doc.xpathEval("//class[name = 'PART']/geom/..//*[name = '%s']//config[type = 'freebsd-ufs']/rawuuid" % name)
        if len(search) > 0:
            return "{uuid}%s" % search[0].content

        search = doc.xpathEval("//class[name = 'LABEL']/geom[name = '%s']/provider/name" % name)
        if len(search) > 0:
            return "{label}%s" % search[0].content

        search = doc.xpathEval("//class[name = 'DEV']/geom[name = '%s']" % name)
        if len(search) > 0:
            return "{devicename}%s" % name

        return None

    def identifier_to_device(self, ident):

        if not ident:
            return None

        doc = self.__geom_confxml()

        search = re.search(r'\{(?P<type>.+?)\}(?P<value>.+)', ident)
        if not search:
            return None

        tp = search.group("type")
        value = search.group("value")

        if tp == 'uuid':
            search = doc.xpathEval("//class[name = 'PART']/geom//config[rawuuid = '%s']/../../name" % value)
            if len(search) > 0:
                for entry in search:
                    if not entry.content.startswith("label"):
                        return entry.content
            return None

        elif tp == 'label':
            search = doc.xpathEval("//class[name = 'LABEL']/geom//provider[name = '%s']/../name" % value)
            if len(search) > 0:
                return search[0].content
            return None

        elif tp == 'serial':
            for devname in self.__get_disks():
                serial = self.serial_from_device(devname)
                if serial == value:
                    return devname
            return None

        elif tp == 'devicename':
            search = doc.xpathEval("//class[name = 'DEV']/geom[name = '%s']" % value)
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
        doc = self.__geom_confxml()
        #TODO get from MBR as well?
        search = doc.xpathEval("//class[name = 'PART']/geom[name = '%s']//config[type = 'freebsd-%s']/../name" % (device, name))
        if len(search) > 0:
            return search[0].content
        else:
            return ''

    def swap_from_identifier(self, ident):
        return self.part_type_from_device('swap', self.identifier_to_device(ident))

    def get_label_provider(self, geom, name):
        doc = self.__geom_confxml()
        providerid = doc.xpathEval("//class[name = 'LABEL']//provider[name = '%s']/../consumer/provider/@ref" % "%s/%s" % (geom, name))[0].content
        provider = doc.xpathEval("//provider[@id = '%s']" % providerid)[0]

        class_name = provider.xpathEval("../../name")[0].content

        # We've got a GPT over the softraid, not raw UFS filesystem
        # So we need to recurse one more time
        if class_name == 'PART':
            providerid = provider.xpathEval("../consumer/provider/@ref")[0].content
            newprovider = doc.xpathEval("//provider[@id = '%s']" % providerid)[0]
            class_name = newprovider.xpathEval("../../name")[0].content
            # if this PART is really backed up by softraid the hypothesis was correct
            if class_name in ('STRIPE', 'MIRROR', 'RAID3'):
                return newprovider

        return provider

    def get_disks_from_provider(self, provider):
        disks = []
        geomname = provider.xpathEval("../../name")[0].content
        if geomname in ('DISK', 'PART'):
            disks.append(provider.xpathEval("../name")[0].content)
        elif geomname in ('STRIPE', 'MIRROR', 'RAID3'):
            doc = self.__geom_confxml()
            for prov in provider.xpathEval("../consumer/provider/@ref"):
                prov2 = doc.xpathEval("//provider[@id = '%s']" % prov.content)[0]
                disks.append(prov2.xpathEval("../name")[0].content)
        else:
            #TODO log, could not get disks
            pass
        return disks

    def zpool_parse(self, name):
        doc = self.__geom_confxml()
        p1 = self.__pipeopen("zpool status %s" % name)
        res = p1.communicate()[0]
        parse = zfs.parse_status(name, doc, res)
        return parse

    def sync_disks(self):
        from storage.models import Disk

        disks = self.__get_disks()
        self.__diskserial.clear()

        in_disks = {}
        serials = []
        for disk in Disk.objects.all():

            dskname = self.identifier_to_device(disk.disk_identifier)
            if not dskname:
                dskname = disk.disk_name
                disk.disk_identifier = self.device_to_identifier(dskname)
                if not disk.disk_identifier:
                    disk.disk_enabled = False
                else:
                    disk.disk_enabled = True
                    disk.disk_serial = self.serial_from_device(dskname)
            elif dskname in in_disks:
                # We are probably dealing with with multipath here
                disk.disk_enabled = False
                continue
            else:
                disk.disk_enabled = True
                if dskname != disk.disk_name:
                    disk.disk_name = dskname

            if disk.disk_serial:
                serials.append(disk.disk_serial)

            if dskname not in disks:
                disk.disk_enabled = False
                if not (disk.disk_enabled or disk._original_state.get("disk_enabled")):
                    #Duplicated disk entries in database
                    disk.delete()
                else:
                    disk.save()
            else:
                disk.save()
            in_disks[dskname] = disk

        for disk in disks:
            if disk not in in_disks:
                d = Disk()
                d.disk_name = disk
                d.disk_identifier = self.device_to_identifier(disk)
                d.disk_serial = self.serial_from_device(disk)
                if d.disk_serial and d.disk_serial in serials:
                    #Probably dealing with multipath here, do not add another
                    continue
                d.save()

    def geom_disks_dump(self, volume):
        #FIXME: This should not be here
        from django.core.urlresolvers import reverse
        from django.utils import simplejson
        from storage.models import Disk
        provider = self.get_label_provider('ufs', volume.vol_name)
        class_name = provider.xpathEval("../../name")[0].content

        items = []
        uid = 1
        if class_name in ('MIRROR', 'RAID3', 'STRIPE'):
            if class_name == 'STRIPE':
                statepath = "../config/State"
                status = provider.xpathEval("../config/Status")[0].content
                ncomponents = int(re.search(r'Total=(?P<total>\d+)', status).group("total"))
            else:
                statepath = "./config/State"
                ncomponents = int(provider.xpathEval("../config/Components")[0].content)
            consumers = provider.xpathEval("../consumer")
            doc = self.__geom_confxml()
            for consumer in consumers:
                provid = consumer.xpathEval("./provider/@ref")[0].content
                status = consumer.xpathEval(statepath)[0].content
                name = doc.xpathEval("//provider[@id = '%s']/../name" % provid)[0].content
                qs = Disk.objects.filter(disk_name=name)
                if qs:
                    actions = {'edit_url': reverse('freeadmin_model_edit',
                        kwargs={
                        'app':'storage',
                        'model': 'Disk',
                        'oid': qs.get().id,
                        })+'?deletable=false'}
                else:
                    actions = {}
                items.append({
                    'type': 'disk',
                    'name': name,
                    'id': uid,
                    'status': status,
                    'actions': simplejson.dumps(actions),
                })
                uid += 1
            for i in xrange(len(consumers), ncomponents):
                #FIXME: This should not be here
                actions = {
                    'replace_url': reverse('storage_geom_disk_replace', kwargs={'vname': volume.vol_name})
                }
                items.append({
                    'type': 'disk',
                    'name': 'UNAVAIL',
                    'id': uid,
                    'status': 'UNAVAIL',
                    'actions': simplejson.dumps(actions),
                })
                uid += 1
        elif class_name == 'PART':
            name = provider.xpathEval("../name")[0].content
            qs = Disk.objects.filter(disk_name=name)
            if qs:
                actions = {'edit_url': reverse('freeadmin_model_edit',
                    kwargs={
                    'app':'storage',
                    'model': 'Disk',
                    'oid': qs.get().id,
                    })+'?deletable=false'}
            else:
                actions = {}
            items.append({
                'type': 'disk',
                'name': name,
                'id': uid,
                'status': 'ONLINE',
                'actions': simplejson.dumps(actions),
            })
        return items


    def __find_root_dev(self):
        """Find the root device.

        The original algorithm was adapted from /root/updatep*, but this
        grabs the relevant information from geom's XML facility.

        Returns:
             The root device name in string format, e.g. FreeNASp1,
             FreeNASs2, etc.

        Raises:
             AssertionError: the root device couldn't be determined.
        """
        # XXX: circular dependency
        import common.system

        sw_name = common.system.get_sw_name()
        doc = self.__geom_confxml()

        for pref in doc.xpathEval("//class[name = 'LABEL']/geom/provider[" \
                "starts-with(name, 'ufs/%s')]/../consumer/provider/@ref" \
                % (sw_name, )):
            prov = doc.xpathEval("//provider[@id = '%s']" % pref.content)[0]
            pid = prov.xpathEval("../consumer/provider/@ref")[0].content
            prov = doc.xpathEval("//provider[@id = '%s']" % pid)[0]
            name = prov.xpathEval("../name")[0].content
            return name
        raise AssertionError('Root device not found (!)')


    def __get_disks(self):
        """Return a list of available storage disks.

        The list excludes all devices that cannot be reserved for storage,
        e.g. the root device, CD drives, etc.

        Returns:
            A list of available devices (ada0, da0, etc), or an empty list if
            no devices could be divined from the system.
        """

        disks = self.sysctl('kern.disks').split()

        root_dev = self.__find_root_dev()

        device_blacklist_re = re.compile('(a?cd[0-9]+|%s)' % (root_dev, ))

        return filter(lambda x: not device_blacklist_re.match(x), disks)


    def zfs_get_version(self):
        """Get the ZFS (SPA) version reported via zfs(4).

        This allows us to better tune warning messages and provide
        conditional support for features in the GUI/CLI.

        Returns:
            An integer corresponding to the version retrieved from zfs(4).

        Raises:
            ValueError: the ZFS version could not be parsed from sysctl(8).
        """

        try:
            version = self.sysctl('vfs.zfs.version.spa', _type='INT')
        except ValueError, ve:
            raise ValueError('Could not determine ZFS version: %s'
                             % (str(ve), ))
        if 0 < version:
            return version
        raise ValueError('Invalid ZFS (SPA) version: %d' % (version, ))

    def __sysctl_error(self, libc, name):
        import errno
        errloc = getattr(libc,'__error')
        errloc.restype = ctypes.POINTER(ctypes.c_int)
        error = errloc().contents.value
        if error == errno.ENOENT:
            msg = "The name is unknown."
        elif error == errno.ENOMEM:
            msg = "The length pointed to by oldlenp is too short to hold " \
                  "the requested value."
        else:
            msg = "Unknown error (%d)" % (error, )
        raise AssertionError("Sysctl by name (%s) failed: %s" % (name, msg))

    def sysctl(self, name, value=None, _type='CHAR'):
        """Get any sysctl value using libc call

        This cut down the overhead of lunching subprocesses

        Returns:
            The value of the given ``name'' sysctl

        Raises:
            AssertionError: sysctlbyname(3) returned an error
        """

        syslog.openlog('middleware', syslog.LOG_CONS | syslog.LOG_PID)
        syslog.syslog(syslog.LOG_NOTICE, "sysctlbyname: %s" % (name, ))

        if value:
            #TODO: set sysctl
            raise NotImplementedError

        libc = ctypes.CDLL('libc.so.7')
        size = ctypes.c_size_t()

        if _type == 'CHAR':
            #We need find out the size
            rv = libc.sysctlbyname(str(name), None, ctypes.byref(size), None, 0)
            if rv != 0:
                self.__sysctl_error(libc, name)

            buf = ctypes.create_string_buffer(size.value)
            arg = buf

        else:
            buf = ctypes.c_int()
            size.value = ctypes.sizeof(buf)
            arg = ctypes.byref(buf)

        # Grab the sysctl value
        rv = libc.sysctlbyname(str(name), arg, ctypes.byref(size), None, 0)
        if rv != 0:
            self.__sysctl_error(libc, name)

        return buf.value

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
