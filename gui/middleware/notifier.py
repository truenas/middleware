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

import ctypes
import types
import syslog
import stat
import os
import re
import glob
import grp
import pwd
import shutil
import signal
from subprocess import Popen, PIPE
import sys
import sqlite3
import tempfile
import time

WWW_PATH = "/usr/local/www"
FREENAS_PATH = os.path.join(WWW_PATH, "freenasUI")
VERSION_FILE = '/etc/version'

sys.path.append(WWW_PATH)
sys.path.append(FREENAS_PATH)

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

from django.db import models

from freenasUI.common.acl import ACL_FLAGS_OS_WINDOWS, ACL_WINDOWS_FILE
from freenasUI.common.freenasacl import ACL, ACL_Hierarchy
from middleware import zfs


class notifier:
    from os import system as ___system
    from pwd import getpwnam as ___getpwnam
    def __system(self, command):
        syslog.openlog("freenas", syslog.LOG_CONS | syslog.LOG_PID)
        syslog.syslog(syslog.LOG_NOTICE, "Executing: " + command)
        # TODO: python's signal class should be taught about sigprocmask(2)
        # This is hacky hack to work around this issue.
        libc = ctypes.cdll.LoadLibrary("libc.so.7")
        omask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        mask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        pmask = ctypes.pointer(mask)
        pomask = ctypes.pointer(omask)
        libc.sigprocmask(3, pmask, pomask)
        self.___system("(" + command + ") 2>&1 | logger -p daemon.notice -t freenas")
        libc.sigprocmask(3, pomask, None)
        syslog.syslog(syslog.LOG_INFO, "Executed: " + command)

    def __system_nolog(self, command):
        retval = 0
        syslog.openlog("freenas", syslog.LOG_CONS | syslog.LOG_PID)
        syslog.syslog(syslog.LOG_NOTICE, "Executing: " + command)
        # TODO: python's signal class should be taught about sigprocmask(2)
        # This is hacky hack to work around this issue.
        libc = ctypes.cdll.LoadLibrary("libc.so.7")
        omask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        mask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        pmask = ctypes.pointer(mask)
        pomask = ctypes.pointer(omask)
        libc.sigprocmask(3, pmask, pomask)
        retval = self.___system("(" + command + ") 2>&1 > /dev/null")
        libc.sigprocmask(3, pomask, None)
        syslog.syslog(syslog.LOG_INFO, "Executed: " + command)
        return retval

    def __pipeopen(self, command):
        syslog.openlog("freenas", syslog.LOG_CONS | syslog.LOG_PID)
        syslog.syslog(syslog.LOG_NOTICE, "Popen()ing: " + command)
        return Popen(command, stdin = PIPE, stdout = PIPE, stderr = PIPE, shell = True, close_fds = True)

    def _do_nada(self):
        pass

    def _simplecmd(self, action, what):
        syslog.openlog("freenas", syslog.LOG_CONS | syslog.LOG_PID)
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
            'afp': ('afpd', '/var/run/afpd.pid'),
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

    def _start_network(self):
        c = self.__open_db()
        c.execute("SELECT COUNT(id) FROM network_interfaces WHERE int_ipv6auto = 1 OR int_ipv6address != ''")
        ipv6_interfaces = c.fetchone()[0]
        if ipv6_interfaces > 0:
            libc = ctypes.cdll.LoadLibrary("libc.so.7")
            auto_linklocal = ctypes.c_uint(0)
            auto_linklocal_size = ctypes.c_uint(4)
            rv = libc.sysctlbyname("net.inet6.ip6.auto_linklocal", ctypes.byref(auto_linklocal), ctypes.byref(auto_linklocal_size), None, 0)
            if rv == 0:
                auto_linklocal = auto_linklocal.value
            else:
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
        self.__system("/usr/sbin/service ix-activedirectory quietstart")
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
        self.__system("/usr/sbin/service ix-kinit quietstart")
        self.__system("/usr/sbin/service ix-activedirectory quietrestart")
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

    def _restart_afp(self):
        self.__system("/usr/sbin/service ix-afpd quietstart")
        self.__system("/usr/sbin/service netatalk forcestop")
        self.__system("/usr/sbin/service dbus forcestop")
        self.__system("/usr/sbin/service dbus restart")
        self.__system("/usr/sbin/service avahi-daemon forcestop")
        self.__system("/usr/sbin/service avahi-daemon restart")
        self.__system("/usr/sbin/service netatalk restart")

    def _reload_afp(self):
        self.__system("/usr/sbin/service ix-afpd quietstart")
        if os.path.isfile("/var/run/afpd.pid"):
            pid = open("/var/run/afpd.pid", "r").read().strip()
            try:
                os.kill(int(pid), signal.SIGHUP)
            except:
                pass
            pid.close()

    def _reload_nfs(self):
        self.__system("/usr/sbin/service ix-nfsd quietstart")
        self.__system("/usr/sbin/service mountd reload")

    def _restart_nfs(self):
        self.__system("/usr/sbin/service mountd forcestop")
        self.__system("/usr/sbin/service nfsd forcestop")
        self.__system("/usr/sbin/service ix-nfsd quietstart")
        self.__system("/usr/sbin/service mountd quietstart")
        self.__system("/usr/sbin/service nfsd quietstart")

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

        # Caculate swap size.
        swapsize = swapsize * 1024 * 1024 * 2
        # Round up to nearest whole integral multiple of 128 and subtract by 34
        # so next partition starts at mutiple of 128.
        swapsize = ((swapsize+127)/128)*128
        # To be safe, wipe out the disk, both ends... before we start
        self.__system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (devname))
        # HACK: force the wipe at the end of the disk to always succeed. This
        # is a lame workaround.
        self.__system("dd if=/dev/zero of=/dev/%s bs=1m oseek=`diskinfo %s "
                      "| awk '{print int($3 / (1024*1024)) - 4;}'` || :" % (devname, devname))

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
                from middleware.exceptions import MiddlewareError
                raise MiddlewareError('Unable to GPT format the disk "%s"' % devname)

        # Install a dummy boot block so system gives meaningful message if booting
        # from the wrong disk.
        return need4khack

    def __gpt_unlabeldisk(self, devname):
        """Unlabel the disk"""
        swapdev = self.swap_from_device(devname)
        if swapdev != '':
            self.__system("swapoff /dev/%s" % self.swap_from_device(devname))
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
            devname = self.identifier_to_device(disk.disk_identifier)
            rv = self.__gpt_labeldisk(type = "freebsd-zfs",
                                      devname = devname,
                                      test4k = (first and test4k),
                                      swapsize=swapsize)
            first = False
            if test4k:
                test4k = False
                want4khack = rv

        self.__confxml = None
        for disk in disks:
            # The identifier {uuid} should now be available
            devname = self.identifier_to_device(disk.disk_identifier)
            ident = self.device_to_identifier(devname)
            if ident != disk.disk_identifier:
                disk.disk_identifier = ident
                disk.save()
            else:
                raise Exception

            devname = self.identifier_to_partition(ident)
            if want4khack:
                self.__system("gnop create -S 4096 /dev/%s" % devname)
                devname = ('/dev/%s.nop' % devname)
                gnop_devs.append(devname)
            else:
                devname = ("/dev/%s" % devname)
            vdevs.append(devname)

        return vdevs, gnop_devs, want4khack

    def __create_zfs_volume(self, volume, swapsize, force4khack=False, path=None):
        """Internal procedure to create a ZFS volume identified by volume id"""
        z_id = volume.id
        z_name = str(volume.vol_name)
        z_vdev = ""
        need4khack = False
        # Grab all disk groups' id matching the volume ID
        vgroup_list = volume.diskgroup_set.all()
        self.__system("swapoff -a")
        gnop_devs = []

        want4khack = force4khack

        for vgrp in vgroup_list:
            vgrp_type = vgrp.group_type
            if vgrp_type != 'stripe':
                z_vdev += " " + vgrp_type
            if vgrp_type in ('cache', 'log'):
                vdev_swapsize = 0
            else:
                vdev_swapsize = swapsize
            # Prepare disks nominated in this group
            vdevs, gnops, want4khack = self.__prepare_zfs_vdev(vgrp.disk_set.all(), vdev_swapsize, want4khack)
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
        p1.wait()
        if p1.returncode != 0:
            from middleware.exceptions import MiddlewareError
            error = ", ".join(p1.communicate()[1].split('\n'))
            raise MiddlewareError('Unable to create the pool: %s' % error)
        self.zfs_inherit_option(z_name, 'mountpoint')

        # If we have 4k hack then restore system to whatever it should be
        if want4khack:
            self.__system("zpool export %s" % (z_name))
            for gnop in gnop_devs:
                self.__system("gnop destroy %s" % gnop)
            self.__system("zpool import -R /mnt %s" % (z_name))

        self.__system("zpool set cachefile=/data/zfs/zpool.cache %s" % (z_name))

    def zfs_volume_attach_group(self, group, force4khack=False):
        """Attach a disk group to a zfs volume"""
        c = self.__open_db()
        c.execute("SELECT adv_swapondrive FROM system_advanced ORDER BY -id LIMIT 1")
        swapsize=c.fetchone()[0]

        volume = group.group_volume
        assert volume.vol_fstype == 'ZFS'
        z_name = volume.vol_name

        z_vdev = ""
        need4khack = False
        # Grab all disk groups' id matching the volume ID
        self.__system("swapoff -a")
        vgrp_type = group.group_type
        if vgrp_type != 'stripe':
            z_vdev += " " + vgrp_type

        # Prepare disks nominated in this group
        vdevs = self.__prepare_zfs_vdev(group.disk_set.all(), swapsize, None)[0]
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
        zfs_output, zfs_err = zfsproc.communicate()
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
            zfsproc = self.__pipeopen("/sbin/zfs list -Hr %s" % (path))
        else:
            zfsproc = self.__pipeopen("/sbin/zfs list -H %s" % (path))
        zfs_output, zfs_err = zfsproc.communicate()
        zfs_output = zfs_output.split('\n')
        retval = {}
        for line in zfs_output:
            if line != "":
               data = line.split('\t')
               retval[data[0]] = data[4]
        return retval

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

    def destroy_zfs_dataset(self, path):
        from freenasUI.common.locks import mntlock
        retval = None
        if '@' in path:
            MNTLOCK = mntlock()
            try:
                MNTLOCK.lock_try()
                zfsproc = self.__pipeopen("zfs get -H freenas:state %s" % (path))
                output = zfsproc.communicate()[0]
                if output != '':
                    fsname, attrname, value, source = output.split('\n')[0].split('\t')
                    if value != '-' and value != 'NEW':
                        retval = 'Held by replication system.'
                MNTLOCK.unlock()
                del MNTLOCK
            except IOError:
                retval = 'Try again later.'
        if retval == None:
            zfsproc = self.__pipeopen("zfs destroy %s" % (path))
            retval = zfsproc.communicate()[1]
            if zfsproc.returncode == 0:
                self.restart("collectd")
        return retval

    def destroy_zfs_vol(self, name):
        zfsproc = self.__pipeopen("zfs destroy %s" % (str(name),))
        retval = zfsproc.communicate()[1]
        return retval

    def __destroy_zfs_volume(self, volume):
        """Internal procedure to destroy a ZFS volume identified by volume id"""
        z_id = volume.id
        z_name = str(volume.vol_name)
        # First, destroy the zpool.
        self.__system("zpool destroy -f %s" % (z_name))

        # Clear out disks associated with the volume
        vgroup_list = volume.diskgroup_set.all()
        for vgrp in vgroup_list:
            vdev_member_list = vgrp.disk_set.all()
            for disk in vdev_member_list:
                devname = self.identifier_to_device(disk.disk_identifier)
                self.__gpt_unlabeldisk(devname = devname)

    def __create_ufs_volume(self, volume, swapsize):
        geom_vdev = ""
        u_id = volume.id
        u_name = str(volume.vol_name)
        ufs_device = ""
        # TODO: We do not support multiple GEOM levels for now.
        vgrp_row = volume.diskgroup_set.all()[0]
        ufs_volume_id = vgrp_row.id
        geom_type = vgrp_row.group_type
        geom_name = vgrp_row.group_name

        if geom_type == '':
            # Grab disk from the group
            disk = vgrp_row.disk_set.all()[0]
            devname = self.identifier_to_device(disk.disk_identifier)
            self.__gpt_labeldisk(type = "freebsd-ufs", devname = devname, swapsize=swapsize)
            self.__confxml = None
            ident = self.device_to_identifier(devname)
            if ident != disk.disk_identifier:
                disk.disk_identifier = ident
                disk.save()
            else:
                raise
            devname = self.identifier_to_partition(ident)
            # TODO: Need to investigate why /dev/gpt/foo can't have label /dev/ufs/bar
            # generated automatically
            p1 = self.__pipeopen("newfs -U -L %s /dev/%s" % (u_name, devname))
            stdout, stderr = p1.communicate()
            if p1.returncode != 0:
                from middleware.exceptions import MiddlewareError
                error = ", ".join(stderr.split('\n'))
                raise MiddlewareError('Volume creation failed: "%s"' % error)
        else:
            # Grab all disks from the group
            vdev_member_list = vgrp_row.disk_set.all()
            for disk in vdev_member_list:
                devname = self.identifier_to_device(disk.disk_identifier)
                # FIXME: turn into a function
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (devname,))
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m oseek=`diskinfo %s "
                      "| awk '{print int($3 / (1024*1024)) - 4;}'`" % (devname, devname))
                geom_vdev += " /dev/" + devname
            self.__system("geom %s load" % (geom_type))
            p1 = self.__pipeopen("geom %s label %s %s" % (geom_type, geom_name, geom_vdev))
            stdout, stderr = p1.communicate()
            if p1.returncode != 0:
                from middleware.exceptions import MiddlewareError
                error = ", ".join(stderr.split('\n'))
                raise MiddlewareError('Volume creation failed: "%s"' % error)
            ufs_device = "/dev/%s/%s" % (geom_type, geom_name)
            self.__system("newfs -U -L %s %s" % (u_name, ufs_device))

    def __destroy_ufs_volume(self, volume):
        """Internal procedure to destroy a UFS volume identified by volume id"""
        u_id = volume.id
        u_name = str(volume.vol_name)

        vgrp = volume.diskgroup_set.all()[0]
        ufs_volume_id = vgrp.id
        geom_type = vgrp.group_type
        geom_name = vgrp.group_name
        if geom_type == '':
            # Grab disk from the group
            disk = vgrp.disk_set.all()[0]
            devname = self.identifier_to_device(disk.disk_identifier)
            self.__system("umount -f /dev/ufs/" + u_name)
            self.__gpt_unlabeldisk(devname = devname)
        else:
            self.__system("swapoff -a")
            self.__system("umount -f /dev/ufs/" + u_name)
            self.__system("geom %s stop %s" % (geom_type, geom_name))
            # Grab all disks from the group
            vdev_member_list = vgrp.disk_set.all()
            for disk in vdev_member_list:
                devname = self.identifier_to_device(disk.disk_identifier)
                disk_name = " /dev/%s" % devname
                self.__system("geom %s clear %s" % (geom_type, disk_name))
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (devname,))
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m oseek=`diskinfo %s "
                      "| awk '{print int($3 / (1024*1024)) - 4;}'`" % (devname, devname))

    def _init_volume(self, volume, *args, **kwargs):
        """Initialize a volume designated by volume_id"""
        c = self.__open_db()
        c.execute("SELECT adv_swapondrive FROM system_advanced ORDER BY -id LIMIT 1")
        swapsize=c.fetchone()[0]
        c.close()

        assert volume.vol_fstype == 'ZFS' or volume.vol_fstype == 'UFS'
        if volume.vol_fstype == 'ZFS':
            self.__create_zfs_volume(volume, swapsize, kwargs.pop('force4khack', False), kwargs.pop('path', None))
        elif volume.vol_fstype == 'UFS':
            self.__create_ufs_volume(volume, swapsize)

    def zfs_replace_disk(self, volume, from_disk, to_disk):
        """Replace disk in volume_id from from_diskid to to_diskid"""
        """Gather information"""
        c = self.__open_db()
        c.execute("SELECT adv_swapondrive FROM system_advanced ORDER BY -id LIMIT 1")
        swapsize=c.fetchone()[0]

        assert volume.vol_fstype == 'ZFS'

        # TODO: Test on real hardware to see if ashift would persist across replace
        fromdev = self.identifier_to_partition(from_disk.disk_identifier)
        fromdev_swap = self.swap_from_identifier(from_disk.disk_identifier)
        zdev = self.device_to_zlabel(fromdev, volume.vol_name)
        if not zdev:
            pool = self.zpool_parse(volume.vol_name)
            unavail = pool[volume.vol_name].find_unavail()
            if len(unavail) >= 1:
                #FIXME: Can we do that if unavail > 1 for _every_ case?
                zdev = unavail[0].name
                from_disk.disk_name = zdev
                from_disk.save()
            else:
                from middleware.exceptions import MiddlewareError
                raise MiddlewareError('An unavail disk could not be found in the pool to be replaced.')

        todev = self.identifier_to_device(to_disk.disk_identifier)

        if fromdev_swap != '':
            self.__system('/sbin/swapoff /dev/%s' % (fromdev_swap))

        if from_disk.id == to_disk.id:
            self.__system('/sbin/zpool offline %s %s' % (volume.vol_name, zdev))

        self.__gpt_labeldisk(type = "freebsd-zfs", devname = todev,
                             swapsize=swapsize)

        self.__confxml = None

        # The identifier {uuid} should now be available
        ident = self.device_to_identifier(todev)
        if ident != to_disk.disk_identifier:
            to_disk.disk_identifier = ident
            to_disk.save()
        else:
            raise Exception
        todev = self.identifier_to_partition(ident)
        todev_swap = self.swap_from_identifier(ident)

        if todev_swap:
            self.__system('/sbin/swapon /dev/%s' % (todev_swap))

        if from_disk.id == to_disk.id:
            self.__system('/sbin/zpool online %s %s' % (volume.vol_name, zdev))
            ret = self.__system_nolog('/sbin/zpool replace %s %s' % (volume.vol_name, zdev))
            if ret == 256:
                ret = self.__system_nolog('/sbin/zpool scrub %s' % (volume.vol_name))
        else:
            p1 = self.__pipeopen('/sbin/zpool replace %s %s %s' % (volume.vol_name, zdev, todev))
            stdout, stderr = p1.communicate()
            ret = p1.returncode
            if ret != 0:
                from middleware.exceptions import MiddlewareError
                error = ", ".join(stderr.split('\n'))
                raise MiddlewareError('Disk replacement failed: "%s"' % error)
        return ret

    def zfs_detach_disk(self, volume, disk):
        """Detach a disk from zpool
           (more technically speaking, a replaced disk.  The replacement actually
           creates a mirror for the device to be replaced)"""

        assert volume.vol_fstype == 'ZFS'

        # TODO: Handle with 4khack aftermath
        devname = disk.identifier_to_partition()
        zlabel = self.device_to_zlabel(devname, volume.vol_name)
        if not zlabel:
            zlabel = disk.disk_name

        # Remove the swap partition for another time to be sure.
        # TODO: swap partition should be trashed instead.
        devname_swap = self.swap_from_device(devname)
        if devname_swap != '':
            self.__system('/sbin/swapoff /dev/%s' % (devname_swap))

        ret = self.__system_nolog('/sbin/zpool detach %s %s' % (volume.vol_name, zlabel))
        # TODO: This operation will cause damage to disk data which should be limited
        self.__gpt_unlabeldisk(devname)
        return ret

    def zfs_add_spare(self, volume_id, disk_id):
        """Add a disk to a zpool as spare"""
        c = self.__open_db()
        c.execute("SELECT vol_fstype, vol_name FROM storage_volume WHERE id = ?",
                 (volume_id,))
        volume = c.fetchone()
        assert volume[0] == 'ZFS' or volume[0] == 'UFS'

        # TODO: Handle with 4khack aftermath
        volume = volume[1]
        c.execute("SELECT disk_name FROM storage_disk WHERE id = ?", (disk_id,))
        devname = 'gpt/' + c.fetchone()[0]

        ret = self.__system_nolog('/sbin/zpool add -f %s spare %s' % (volume, devname))
        return ret

    def detach_volume_swaps(self, volume):
        """Detach all swaps associated with volume"""
        vgroup_list = volume.diskgroup_set.all()
        for vgrp in vgroup_list:
            vdev_member_list = vgrp.disk_set.all()
            for disk in vdev_member_list:
                devname = self.identifier_to_device(disk.disk_identifier)
                swapdev = self.swap_from_device(devname)
                if swapdev != '':
                    self.__system("swapoff /dev/%s" % self.swap_from_device(devname))

    def _destroy_volume(self, volume):
        """Destroy a volume designated by volume_id"""

        assert volume.vol_fstype in ('ZFS', 'UFS', 'iscsi', 'NTFS', 'MSDOSFS', 'EXT2FS')
        if volume.vol_fstype == 'ZFS':
            self.__destroy_zfs_volume(volume)
        elif volume.vol_fstype == 'UFS':
            self.__destroy_ufs_volume(volume)
        self._reload_disk()

    def _reload_disk(self):
        self.__system("/usr/sbin/service ix-smartd quietstart")
        self.__system("/usr/sbin/service smartd restart")
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
            from freenasUI.middleware.exceptions import MiddlewareError
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
        dirty = False
        homedir = str(homedir)
        pubkey = str(pubkey)
        if pubkey[-1] != '\n':
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
        hier.set_defaults(recursive)
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

    def change_upload_location(self, path):
        self.__system("/bin/rm -rf /var/tmp/firmware")
        self.__system("/bin/mkdir -p %s/.freenas" % path)
        self.__system("/usr/sbin/chown www:www %s/.freenas" % path)
        self.__system("/bin/ln -s %s/.freenas /var/tmp/firmware" % path)

    def validate_xz(self, path):
        ret = self.__system_nolog("/usr/bin/xz -t %s" % (path))
        if ret == 0:
            return True
        return False

    def update_firmware(self, path):
        self.__system("/usr/bin/xz -cd %s | sh /root/update && touch /data/need-update" % (path))
        self.__system("/bin/rm -fr /var/tmp/firmware/firmware.xz")

    def apply_servicepack(self):
        self.__system("/usr/bin/xz -cd /var/tmp/firmware/servicepack.txz | /usr/bin/tar xf - -C /var/tmp/firmware/ etc/servicepack/version.expected")
        try:
            with open(VERSION_FILE) as f:
                freenas_build = f.read()
        except:
            return 'Could not determine software version from service pack'
        try:
            with open('/var/tmp/firmware/etc/servicepack/version.expected') as f:
                expected_build = f.read()
        except:
            return 'Invalid software version in service pack'
        if freenas_build != expected_build:
            return 'Software versions did not match ("%s" != "%s")' % \
                (freenas_build, expected_build)
        self.__system("/sbin/mount -uw /")
        self.__system("/usr/bin/xz -cd /var/tmp/firmware/servicepack.txz | /usr/bin/tar xf - -C /")
        self.__system("/bin/sh /etc/servicepack/post-install")
        self.__system("/bin/rm -fr /var/tmp/firmware/servicepack.txz")
        self.__system("/bin/rm -fr /var/tmp/firmware/etc")

    def get_volume_status(self, name, fs, group_type):
        status = 'UNKNOWN'
        if fs == 'ZFS':
            status = self.__pipeopen('zpool list -H -o health %s' % name.__str__()).communicate()[0].strip('\n')
        elif fs == 'UFS':
            gtype = None
            for gtypes in group_type:
                if 'mirror' == gtypes[0]:
                    gtype = 'MIRROR'
                    break
                elif 'stripe' == gtypes[0]:
                    gtype = 'STRIPE'
                    break
                elif 'raid3' == gtypes[0]:
                    gtype = 'RAID3'
                    break

            if gtype in ('MIRROR', 'STRIPE', 'RAID3'):

                doc = self.__geom_confxml()
                search = doc.xpathEval("//class[name = '%s']/geom[name = '%s']/config/State" % (gtype, name))
                if len(search) > 0:
                    status = search[0].content

                else:
                    search = doc.xpathEval("//class[name = '%s']/geom[name = '%s%s']/config/State" % (gtype, name, gtype.lower()))
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
        hasher=self.__pipeopen('%s %s' % (algorithm2map[algorithm], path))
        sum=hasher.communicate()[0].split('\n')[0]
        return sum

    def get_disks(self):
        disks = self.__pipeopen("/sbin/sysctl -n kern.disks").communicate()[0].strip('\n').split(' ')
        regexp_nocamcdrom = re.compile('^cd[0-9]')

        disksd = {}

        for disk in disks:
            if regexp_nocamcdrom.match(disk) == None:
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
                        'devname': info[0].split('/')[-1],
                        'capacity': info[2]
                    },
                })
        return partitions

    def precheck_partition(self, dev, fstype):

        if fstype == 'UFS':
            p1 = Popen(["/sbin/fsck_ufs", "-p", dev], stdin=PIPE, stdout=PIPE)
            p1.wait()
            if p1.returncode == 0:
                return True
        elif fstype == 'NTFS':
            return True
        elif fstype == 'MSDOSFS':
            p1 = Popen(["/sbin/fsck_msdosfs", "-p", dev], stdin=PIPE, stdout=PIPE)
            p1.wait()
            if p1.returncode == 0:
                return True
        elif fstype == 'EXT2FS':
            p1 = Popen(["/sbin/fsck_ext2fs", "-p", dev], stdin=PIPE, stdout=PIPE)
            p1.wait()
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
            p1.wait()
            if p1.returncode == 0:
                return True
        elif fstype == 'NTFS':
            p1 = Popen(["/usr/local/sbin/ntfslabel", dev, label], stdin=PIPE, stdout=PIPE)
            p1.wait()
            if p1.returncode == 0:
                return True
        elif fstype == 'MSDOSFS':
            p1 = Popen(["/usr/local/bin/mlabel", "-i", dev, "::%s" % label], stdin=PIPE, stdout=PIPE)
            p1.wait()
            if p1.returncode == 0:
                return True
        elif fstype == 'EXT2FS':
            p1 = Popen(["/usr/local/sbin/tune2fs", "-L", label, dev], stdin=PIPE, stdout=PIPE)
            p1.wait()
            if p1.returncode == 0:
                return True
        elif fstype is None:
            p1 = Popen(["/sbin/geom", "label", "label", label, dev], stdin=PIPE, stdout=PIPE)
            p1.wait()
            if p1.returncode == 0:
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
                    disks.append( device[0].content )
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
                    'log': roots['log'].dump() if roots['log'] else None,
                    'spare': roots['spare'].dump() if roots['spare'] else None,
                    'disks': roots[pool].dump(),
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
            from middleware.exceptions import MiddlewareError
            raise MiddlewareError('Unable to export %s: %s' % (name, stderr))
        return True

    def zfs_snapshot_list(self):
        fsinfo = dict()

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
                snaplist.insert(0, dict([('fullname', snapname), ('name', name), ('used', used), ('refer', refer), ('mostrecent', mostrecent)]))
                fsinfo[fs] = snaplist
        return fsinfo

    def zfs_mksnap(self, path, name, recursive):
        if recursive:
            retval = self.__system_nolog("/sbin/zfs snapshot -r %s@%s" % (path, name))
        else:
            retval = self.__system_nolog("/sbin/zfs snapshot %s@%s" % (path, name))
        return retval

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
        open('/data/need-update', 'w+').close()

        return True

    def zfs_get_options(self, name):
        data = {}
        noinherit_fields = ['quota', 'refquota', 'reservation', 'refreservation']
        zfsname = str(name)

        zfsproc = self.__pipeopen("/sbin/zfs get -H -o property,value,source all %s" % (zfsname))
        zfs_output, zfs_err = zfsproc.communicate()
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
        from freenasUI.common.locks import mntlock
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
        from freenasUI.common.locks import mntlock
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

    def geom_disk_state(self, geom, group_type, devname):
        if group_type:
            p1 = self.__pipeopen("geom %s list %s" % (str(group_type), str(geom)))
            output = p1.communicate()[0]
            reg = re.search(r'^\d\. Name: %s.*?State: (?P<state>\w+)' % devname, output, re.S|re.I|re.M)
            if reg:
                return reg.group("state")
            else:
                return "FAILED"

    def geom_disk_replace(self, volume, from_disk, to_disk):
        """Replace disk in volume_id from from_diskid to to_diskid"""
        """Gather information"""

        assert volume.vol_fstype == 'UFS'

        todev = to_disk.identifier_to_device()

        dg = from_disk.disk_group
        group_name = dg.group_name
        group_type = dg.group_type

        if group_type == "mirror":
            rv = self.__system_nolog("geom mirror forget %s" % (str(group_name),))
            if rv != 0:
                return rv
            rv = self.__system_nolog("geom mirror insert %s /dev/%s" % (str(group_name), str(todev),))
            return rv

        elif group_type == "raid3":
            p1 = self.__pipeopen("geom raid3 list %s" % str(group_name))
            output = p1.communicate()[0]
            components = range(int(re.search(r'Components: (?P<num>\d+)', output).group("num")))
            filled = [int(i) for i in re.findall(r'Number: (?P<number>\d+)', output)]
            lacking = [x for x in components if x not in filled][0]
            rv = self.__system_nolog("geom raid3 insert -n %d %s %s" % \
                                        (lacking, str(group_name), str(todev),))
            return rv

        return 1

    def vlan_delete(self, vint):
        self.__system("ifconfig %s destroy" % vint)

    def zfs_sync_datasets(self, volume):
        c, conn = self.__open_db(True)
        vol_name = str(volume.vol_name)
        c.execute("SELECT mp_path FROM storage_mountpoint WHERE mp_volume_id = ?", (volume.id,))
        mp = volume.mountpoint_set.all()[0]
        mp_path = str(mp.mp_path)

        c.execute("DELETE FROM storage_mountpoint WHERE mp_ischild = 1 AND mp_volume_id = %s" % str(volume.id))

        # Reset mountpoints on the whole volume
        self.zfs_inherit_option(vol_name, 'mountpoint', True)

        p1 = self.__pipeopen("zfs list -t filesystem -o name -H -r %s" % str(vol_name))
        ret = p1.communicate()[0].split('\n')[1:-1]
        for dataset in ret:
            name = "/".join(dataset.split('/')[1:])
            mp = os.path.join(mp_path, name)
            c.execute("INSERT INTO storage_mountpoint (mp_volume_id, mp_path, mp_options, mp_ischild) VALUES (?, ?, ?, ?)", (volume.id, mp, "noauto", "1"), )
        conn.commit()
        c.close()

    def __init__(self):
        self.__confxml = None

    def __geom_confxml(self):
        if self.__confxml == None:
            from libxml2 import parseDoc
            sysctl_proc = self.__pipeopen('sysctl -b kern.geom.confxml')
            self.__confxml = parseDoc(sysctl_proc.communicate()[0][:-1])
        return self.__confxml

    def serial_from_device(self, devname):
        p1 = Popen(["/usr/local/sbin/smartctl", "-i", "/dev/%s" % devname], stdout=PIPE)
        output = p1.communicate()[0]
        search = re.search(r'^Serial Number:[ \t\s]+(?P<serial>.+)', output, re.I|re.M)
        if search:
            return search.group("serial")
        return None

    def device_to_identifier(self, name):
        name = str(name)
        doc = self.__geom_confxml()

        search = doc.xpathEval("//class[name = 'PART']/..//*[name = '%s']//config[type = 'freebsd-zfs']/rawuuid" % name)
        if len(search) > 0:
            return "{uuid}%s" % search[0].content
        search = doc.xpathEval("//class[name = 'PART']/geom/..//*[name = '%s']//config[type = 'freebsd-ufs']/rawuuid" % name)
        if len(search) > 0:
            return "{uuid}%s" % search[0].content

        search = doc.xpathEval("//class[name = 'LABEL']/geom[name = '%s']/provider/name" % name)
        if len(search) > 0:
            return "{label}%s" % search[0].content

        serial = self.serial_from_device(name)
        if serial:
            return "{serial}%s" % serial

        return "{devicename}%s" % name

    def identifier_to_device(self, ident):
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
            p1 = Popen(["sysctl", "-n", "kern.disks"], stdout=PIPE)
            output = p1.communicate()[0]
            for devname in output.split(' '):
                serial = self.serial_from_device(devname)
                if serial == value:
                    return devname
            return None

        elif tp == 'devicename':
            return value
        else:
            raise NotImplementedError

    def identifier_to_partition(self, ident):
        doc = self.__geom_confxml()

        search = re.search(r'\{(?P<type>.+?)\}(?P<value>.+)', ident)
        if not search:
            return None

        tp = search.group("type")
        value = search.group("value")

        if tp == 'uuid':
            search = doc.xpathEval("//class[name = 'PART']/geom//config[rawuuid = '%s']/../name" % value)
            if len(search) > 0:
                return search[0].content

        elif tp == 'label':
            search = doc.xpathEval("//class[name = 'LABEL']/geom//provider[name = '%s']/../name" % value)
            if len(search) > 0:
                return search[0].content

        elif tp == 'devicename':
            return value
        else:
            raise NotImplementedError

    def swap_from_device(self, device):
        doc = self.__geom_confxml()
        search = doc.xpathEval("//class[name = 'PART']/geom[name = '%s']//config[type = 'freebsd-swap']/../name" % device)
        if len(search) > 0:
            return search[0].content
        else:
            return ''

    def swap_from_identifier(self, ident):
        return self.swap_from_device(self.identifier_to_device(ident))

    def device_to_zlabel(self, devname, pool):
        status = self.__pipeopen("zpool status %s" % (str(pool),)).communicate()[0]

        doc = self.__geom_confxml()
        search = doc.xpathEval("//class[name = 'LABEL']/geom[name = '%s']//provider/name" % devname)

        for entry in search:
            if re.search(r'\b%s\b' % entry.content, status):
                return entry.content
        if re.search(r'\b%s\b' % devname, status):
            return devname
        return None

    def filesystem_path(self, path):
        from storage.models import MountPoint
        mps = MountPoint.objects.filter(mp_volume__vol_fstype__in=('ZFS','UFS'))
        path = os.path.abspath(path)
        for mp in mps:
            if path.startswith(os.path.abspath(mp.mp_path)):
                return mp.mp_volume.vol_fstype
        return 'UFS'

    def zpool_parse(self, name):
        doc = self.__geom_confxml()
        p1 = self.__pipeopen("zpool status %s" % name)
        res = p1.communicate()[0]
        parse = zfs.parse_status(name, doc, res)
        return parse

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
    if len(sys.argv) < 3:
        usage()
    else:
        n = notifier()
        f = getattr(n, sys.argv[1], None)
        if f is None:
            sys.stderr.write("Unknown action: %s\n" % sys.argv[1])
            usage()
        print f(*sys.argv[2:])
