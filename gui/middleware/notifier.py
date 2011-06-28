#!/usr/bin/env python
#-
# Copyright (c) 2010 iXsystems, Inc.
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
import signal
import time
import sys
from subprocess import Popen, PIPE

WWW_PATH = "/usr/local/www"
FREENAS_PATH = os.path.join(WWW_PATH, "freenasUI")

sys.path.append(WWW_PATH)
sys.path.append(FREENAS_PATH)

os.environ["DJANGO_SETTINGS_MODULE"] = "freenasUI.settings"

from django.db import models

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
        try:
            f = getattr(self, '_' + action + '_' + what)
        except AttributeError:
            """ Provide generic start/stop/restart verbs for rc.d scripts """
            if action in ("start", "stop", "restart", "reload"):
                if action == 'restart':
                    self.__system("/usr/sbin/service " + what + " forcestop ")
                self.__system("/usr/sbin/service " + what + " " + action)
                f = self._do_nada
            else:
                raise "Internal error: Unknown command"
        try:
            f()
        except:
            raise

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
            try:
                f = getattr(self, '_init_' + what)
                f(objectid, *args, **kwargs)
            except:
                raise

    def destroy(self, what, objectid = None):
        if objectid == None:
            raise ValueError("Calling destroy without id")
        else:
            try:
                f = getattr(self, '_destroy_' + what)
                f(objectid)
            except:
                raise

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

    def _reload_iscsitarget(self):
        self.__system("/usr/sbin/service ix-istgt quietstart")
        self.__system("/usr/sbin/service istgt reload")

    def _start_network(self):
        # TODO: Skip this step when IPv6 is already enabled
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
        ret = False
        from freenasUI.common.freenasldap import FreeNAS_LDAP
        c = self.__open_db()
        c.execute("SELECT srv_enable FROM services_services WHERE srv_service='ldap' ORDER BY -id LIMIT 1")
        enabled = c.fetchone()[0]
        if enabled == 1:
            c.execute("SELECT ldap_hostname,ldap_rootbasedn,ldap_rootbindpw,ldap_basedn,ldap_ssl FROM services_ldap ORDER BY -id LIMIT 1")
            host, rootbasedn, pw, basedn, ssl = c.fetchone()
            f = FreeNAS_LDAP(host, rootbasedn, pw, basedn, ssl)
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

    def _started_activedirectory(self):
        ret = False
        from freenasUI.common.freenasldap import FreeNAS_LDAP
        c = self.__open_db()
        c.execute("SELECT srv_enable FROM services_services WHERE srv_service='activedirectory' ORDER BY -id LIMIT 1")
        enabled = c.fetchone()[0]
        if enabled == 1:
            c.execute("SELECT ad_dcname,ad_domainname,ad_adminname,ad_adminpw FROM services_activedirectory ORDER BY -id LIMIT 1")
            ad_dcname,ad_domainname,ad_adminname,ad_adminpw = c.fetchone()
            #base = ','.join(["dc=%s" % part for part in ad_domainname.split(".")])
            f = FreeNAS_LDAP(ad_dcname, ad_adminname+"@"+ad_domainname, ad_adminpw)
            f.basedn = f.get_active_directory_baseDN()
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

    def _stop_ups(self):
        self.__system("/usr/sbin/service nut stop")

    def _restart_ups(self):
        self.__system("/usr/sbin/service ix-ups quietstart")
        self.__system("/usr/sbin/service nut restart")

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
        self.__system("/usr/sbin/service nfsd quietstart")

    def _restart_dynamicdns(self):
        self.__system("/usr/sbin/service ix-inadyn quietstart")
        self.__system("/usr/sbin/service inadyn restart")

    def _restart_system(self):
        self.__system("/bin/sleep 3 && /sbin/shutdown -r now &")

    def _stop_system(self):
        self.__system("/sbin/shutdown -p now")

    def _reload_cifs(self):
        self.__system("/usr/sbin/service ix-samba quietstart")
        self.__system("/usr/sbin/service samba reload")

    def _restart_cifs(self):
        # TODO: bug in samba rc.d script
        # self.__system("/usr/sbin/service samba forcestop")
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
        import sqlite3

        conn = sqlite3.connect(dbname)
        c = conn.cursor()
        if ret_conn:
            return c, conn
        return c

    def __gpt_labeldisk(self, type, devname, label = "", swapsize=2):
        """Label the whole disk with GPT under the desired label and type"""
        # Taste the disk to know whether it's 4K formatted.
        # requires > 8.1-STABLE after r213467
        ret_4kstripe = self.__system_nolog("geom disk list %s "
                                           "| grep 'Stripesize: 4096'" % (devname))
        ret_512bsector = self.__system_nolog("geom disk list %s "
                                             "| grep 'Sectorsize: 512'" % (devname))
        # Make sure that the partition is 4k-aligned, if the disk reports 512byte sector
        # while using 4k stripe, use an offset of 64.
        need4khack = (ret_4kstripe == 0) and (ret_512bsector == 0)
        # Caculate swap size.
        swapsize = swapsize * 1024 * 1024 * 2
        # Round up to nearest whole integral multiple of 128 and subtract by 34
        # so next partition starts at mutiple of 128.
        swapsize = ((swapsize+127)/128)*128
        # To be safe, wipe out the disk, both ends... before we start
        self.__system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (devname))
        self.__system("dd if=/dev/zero of=/dev/%s bs=1m oseek=`diskinfo %s "
                      "| awk '{print int($3 / (1024*1024)) - 4;}'`" % (devname, devname))
        if label != "":
            p1 = self.__pipeopen("gpart create -s gpt /dev/%s && gpart add -b 128 -t freebsd-swap -l swap-%s -s %d %s && gpart add -t %s -l %s %s" %
                         (str(devname), str(label), swapsize, str(devname), str(type), str(label), str(devname)))
        else:
            p1 = self.__pipeopen("gpart create -s gpt /dev/%s && gpart add -b 128 -t freebsd-swap -s %d %s && gpart add -t %s %s" %
                         (str(devname), swapsize, str(devname), str(type), str(devname)))
        p1.wait()
        if p1.returncode != 0:
            from middleware.exceptions import MiddlewareError
            raise MiddlewareError('Unable to GPT format the disk "%s"' % devname)
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

    def __create_zfs_volume(self, volume, swapsize, force4khack=False):
        """Internal procedure to create a ZFS volume identified by volume id"""
        z_id = volume.id
        z_name = str(volume.vol_name)
        z_vdev = ""
        need4khack = False
        # Grab all disk groups' id matching the volume ID
        vgroup_list = volume.diskgroup_set.all()
        self.__system("swapoff -a")
        for vgrp in vgroup_list:
            hack_vdevs = []
            vgrp_type = vgrp.group_type
            if vgrp_type != 'stripe':
                z_vdev += " " + vgrp_type
            # Grab all member disks from the current vdev group
            vdev_member_list = vgrp.disk_set.all()
            for disk in vdev_member_list:
                devname = self.identifier_to_device(disk.disk_identifier)
                need4khack = self.__gpt_labeldisk(type = "freebsd-zfs",
                                                  devname = devname,
                                                  label = "",
                                                  swapsize=swapsize)
                # The identifier {uuid} should now be available
                ident = self.device_to_identifier(devname)
                if ident != disk.disk_identifier:
                    disk.disk_identifier = ident
                    disk.save()
                else:
                    raise Exception
                devname = self.identifier_to_partition(ident)

                if need4khack or force4khack:
                    hack_vdevs.append(devname)
                    self.__system("gnop create -S 4096 /dev/%s" % devname)
                    z_vdev += " /dev/%s.nop" % devname
                else:
                    z_vdev += " /dev/%s" % devname
        self._reload_disk()
        # Finally, create the zpool.
        # TODO: disallowing cachefile may cause problem if there is
        # preexisting zpool having the exact same name.
        if not os.path.isdir("/data/zfs"):
            os.makedirs("/data/zfs")
        p1 = self.__pipeopen("zpool create -o cachefile=/data/zfs/zpool.cache "
                      "-f -m /mnt/%s -o altroot=/mnt %s %s" % (z_name, z_name, z_vdev))
        p1.wait()
        if p1.returncode != 0:
            from middleware.exceptions import MiddlewareError
            error = ", ".join(p1.communicate()[1].split('\n'))
            raise MiddlewareError('Unable to create the pool: %s' % error)
        self.zfs_inherit_option(z_name, 'mountpoint')
        # If we have 4k hack then restore system to whatever it should be
        if need4khack or force4khack:
            self.__system("zpool export %s" % (z_name))
            for disk in hack_vdevs:
                self.__system("gnop destroy /dev/%s.nop" % disk)
            self.__system("zpool import -R /mnt %s" % (z_name))

        self.__system("zpool set cachefile=/data/zfs/zpool.cache %s" % (z_name))

        # These should probably be options that are configurable from the GUI
        self.__system("zfs set aclmode=passthrough %s" % z_name)
        self.__system("zfs set aclinherit=passthrough %s" % z_name)

    # TODO: This is a rather ugly hack and duplicates some code, need to
    # TODO: cleanup this with the __create_zfs_volume.
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
        # Grab all member disks from the current vdev group
        vdev_member_list = group.disk_set.all()
        for disk in vdev_member_list:
            devname = self.identifier_to_device(disk.disk_identifier)
            need4khack = self.__gpt_labeldisk(type = "freebsd-zfs",
                                              devname = devname,
                                              label = "",
                                              swapsize=swapsize)
            # The identifier {uuid} should now be available
            ident = self.device_to_identifier(devname)
            if ident != disk.disk_identifier:
                disk.disk_identifier = ident
                disk.save()
            else:
                raise
            devname = self.identifier_to_partition(ident)

            if need4khack or force4khack:
                self.__system("gnop create -S 4096 /dev/%s" % devname)
                z_vdev += " /dev/%s.nop" % devname
            else:
                z_vdev += " /dev/%s" % devname
        self._reload_disk()
        # Finally, attach new groups to the zpool.
        self.__system("zpool add %s %s" % (z_name, z_vdev))

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

    def get_zfs_attributes(self, zfsname):
        """Return a dictionary that contains all ZFS attributes"""
        zfsproc = self.__pipeopen("/sbin/zfs get -H all %s" % (zfsname))
        zfs_output, zfs_err = zfsproc.communicate()
        zfs_output = zfs_output.split('\n')
        retval = {}
        for line in zfs_output:
            if line != "":
                data = line.split('\t')
                retval[data[1]] = data[2]
        return retval
    def set_zfs_attribute(self, name, attr, value):
        self.__system("zfs set %s=%s %s" % (attr, value, name))

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
        self._reload_disk()

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
            p1.wait()
            if p1.returncode != 0:
                from middleware.exceptions import MiddlewareError
                error = ", ".join(p1.communicate()[1].split('\n'))
                raise MiddlewareError('Volume creation failed: "%s"' % error)
        else:
            # Grab all disks from the group
            vdev_member_list = vgrp_row.disk_set.all()
            for disk in vdev_member_list:
                devname = self.identifier_to_device(disk.disk_identifier)
                geom_vdev += " /dev/" + devname
            self.__system("geom %s load" % (geom_type))
            p1 = self.__pipeopen("geom %s label %s %s" % (geom_type, geom_name, geom_vdev))
            p1.wait()
            if p1.returncode != 0:
                from middleware.exceptions import MiddlewareError
                error = ", ".join(p1.communicate()[1].split('\n'))
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
        self._reload_disk()

    def _init_volume(self, volume, *args, **kwargs):
        """Initialize a volume designated by volume_id"""
        c = self.__open_db()
        c.execute("SELECT adv_swapondrive FROM system_advanced ORDER BY -id LIMIT 1")
        swapsize=c.fetchone()[0]
        c.close()

        assert volume.vol_fstype == 'ZFS' or volume.vol_fstype == 'UFS'
        if volume.vol_fstype == 'ZFS':
            self.__create_zfs_volume(volume, swapsize, kwargs.pop('force4khack', False))
        elif volume.vol_fstype == 'UFS':
            self.__create_ufs_volume(volume, swapsize)
        self._reload_disk()

    def _init_zfs_disk(self, disk_id):
        """Initialize a disk designated by disk_id"""
        """notifier().init("disk", 1)"""
        c = self.__open_db()
        c.execute("SELECT adv_swapondrive FROM system_advanced ORDER BY -id LIMIT 1")
        swapsize=c.fetchone()[0]
        c.execute("SELECT disk_identifier, disk_name FROM storage_disk WHERE id = ?", (disk_id,))
        disk = c.fetchone()
        devname = self.identifier_to_device(disk[0])
        self.__gpt_labeldisk(type = "freebsd-zfs", devname = devname,
                             label = disk[1], swapsize=swapsize)

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
        zdev = self.device_to_zlabel(fromdev, volume.vol_name) or fromdev

        todev = self.identifier_to_device(to_disk.disk_identifier)

        if fromdev_swap != '':
            self.__system('/sbin/swapoff /dev/%s' % (fromdev_swap))

        if from_disk.id == to_disk.id:
            self.__system('/sbin/zpool offline %s %s' % (volume, zdev))

        self.__gpt_labeldisk(type = "freebsd-zfs", devname = todev,
                             label = "", swapsize=swapsize)

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
            p1.wait()
            ret = p1.returncode
            if ret != 0:
                from middleware.exceptions import MiddlewareError
                error = ", ".join(p1.communicate()[1].split('\n'))
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

        ret = self.__system_nolog('/sbin/zpool add %s spare %s' % (volume, devname))
        return ret

    def _destroy_volume(self, volume):
        """Destroy a volume designated by volume_id"""

        assert volume.vol_fstype in ('ZFS', 'UFS', 'iscsi', 'NTFS', 'MSDOSFS', 'EXT2FS')
        if volume.vol_fstype == 'ZFS':
            self.__destroy_zfs_volume(volume)
        elif volume.vol_fstype == 'UFS':
            self.__destroy_ufs_volume(volume)

    def _reload_disk(self):
        self.__system("/usr/sbin/service ix-smartd quietstart")
        self.__system("/usr/sbin/service smartd restart")
        self.__system("/usr/sbin/service ix-fstab quietstart")
        self.__system("/usr/sbin/service swap1 quietstart")
        self.__system("/usr/sbin/service mountlate quietstart")

    # Create a user in system then samba
    def __pw_with_password(self, command, password):
        pw = self.__pipeopen(command)
        msg = pw.communicate("%s\n" % password)[1]
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
                    shell = "/sbin/nologin", homedir = "/mnt", password_disabled=False):
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
        if password_disabled:
            smb_hash = ""
        else:
            smb_command = "/usr/local/bin/pdbedit -w %s" % username
            smb_cmd = self.__pipeopen(smb_command)
            smb_hash = smb_cmd.communicate()[0].split('\n')[0]
        user = self.___getpwnam(username)
        return (user.pw_uid, user.pw_gid, user.pw_passwd, smb_hash)

    def user_lock(self, username):
        self.__system('/usr/sbin/pw lock "%s"' % (username))
        user = self.___getpwnam(username)
        return user.pw_passwd

    def user_unlock(self, username):
        self.__system('/usr/sbin/pw unlock "%s"' % (username))
        user = self.___getpwnam(username)
        return user.pw_passwd

    def user_changepassword(self, username, password):
        """Changes user password"""
        command = '/usr/sbin/pw usermod "%s" -h 0' % (username)
        self.__issue_pwdchange(username, command, password)
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

    def _reload_user(self):
        self.__system("/usr/sbin/service ix-passwd quietstart")
        self.__system("/usr/sbin/service ix-aliases quietstart")
        self.reload("cifs")

    def __make_windows_happy(self, path='/mnt', user='root', group='wheel',
                             mode='0755', recursive=False):
        self.__system("/bin/setfacl -b '%s'" % path)
        self.__system("for i in $(jot 5); do setfacl -x 0 '%s'; done" % path)
        self.__system("/bin/setfacl -a 0 group@:rxs::allow '%s'" % path)
        self.__system("/bin/setfacl -a 1 everyone@:rxaRcs::allow '%s'" % path)
        self.__system("/bin/setfacl -a 2 owner@:rwxpdDaARWcCo:fd:allow '%s'" % path)
        self.__system("/bin/setfacl -x 3 '%s'" % path)

    def mp_change_permission(self, path='/mnt', user='root', group='wheel',
                             mode='0755', recursive=False):
        if recursive:
            flags='-R '
        else:
            flags=''
        self.__system("/usr/sbin/chown %s'%s':'%s' %s" % (flags, user, group, path))
        self.__system("/bin/chmod %s%s %s" % (flags, mode, path))
        self.__make_windows_happy(path, user, group, mode, recursive)

    def mp_get_permission(self, path):
        if os.path.isdir(path):
            return stat.S_IMODE(os.stat(path)[stat.ST_MODE])

    def mp_get_owner(self, path):
        if os.path.isdir(path):
            stat_info = os.stat(path)
            uid = stat_info.st_uid
            gid = stat_info.st_gid
            try:
                user = pwd.getpwuid(uid)[0]
            except KeyError:
                user = 'root'
                self.__system("/usr/bin/chown %s %s" % (user, path))
            try:
                group = grp.getgrgid(gid)[0]
            except KeyError:
                group = 'wheel'
                self.__system("/usr/bin/chown :%s %s" % (group, path))
            return [user, group]

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
            f = open('/etc/version.freenas', 'r')
            freenas_build = f.read()
            f.close()
        except:
            return "Current FreeNAS version can not be recognized"
        try:
            f = open('/var/tmp/firmware/etc/servicepack/version.expected', 'r')
            expected_build = f.read()
            f.close()
        except:
            return "Expected FreeNAS version can not be recognized"
        if freenas_build != expected_build:
            return "Can not apply service pack because version mismatch"
        self.__system("/sbin/mount -uw /")
        self.__system("/usr/bin/xz -cd /var/tmp/firmware/servicepack.txz | /usr/bin/tar xf - -C /")
        self.__system("/bin/sh /etc/servicepack/post-install")
        self.__system("/bin/rm -fr /var/tmp/firmware/servicepack.txz")
        self.__system("/bin/rm -fr /var/tmp/firmware/etc")

    def get_volume_status(self, name, fs, group_type):
        if fs == 'ZFS':
            result = self.__pipeopen('zpool list -H -o health %s' % name.__str__()).communicate()[0].strip('\n')
            return result
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
                    return search[0].content

                search = doc.xpathEval("//class[name = '%s']/geom[name = '%s%s']/config/State" % (gtype, name, gtype.lower()))
                if len(search) > 0:
                    return search[0].content

        return 'UNKNOWN'

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
            p1 = Popen(["/usr/local/bin/ntfsfix", dev], stdin=PIPE, stdout=PIPE)
            p1.wait()
            if p1.returncode == 0:
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

        class Tnode(object):
            name = None
            leaf = False
            children = None
            parent = None
            type = None

            def __init__(self, name, doc):
                self._doc = doc
                self.name = name
                self.children = []

            def find_by_name(self, name):
                for c in self.children:
                    if c.name == name:
                        return c
                return None

            def append(self, tnode):
                self.children.append(tnode)
                tnode.parent = self

            @staticmethod
            def pprint(node, level=0):
                print '   ' * level + node.name
                for c in node.children:
                    node.pprint(c, level+1)

            def __repr__(self):
                if not self.parent:
                    return "<Section: %s>" % self.name
                return "<Node: %s>" % self.name

            def _is_vdev(self, name):
                if name in ('stripe', 'mirror', 'raidz', 'raidz1', 'raidz2', 'raidz3') \
                    or re.search(r'^(mirror|raidz|raidz1|raidz2|raidz3)(-\d+)?$', name):
                    return True
                return False

            def __iter__(self):
                for c in list(self.children):
                    yield c

            def _vdev_type(self, name):
                if name.startswith('stripe'):
                    return "stripe"
                elif name.startswith('mirror'):
                    return "mirror"
                elif name.startswith("raidz3"):
                    return "raidz3"
                elif name.startswith("raidz2"):
                    return "raidz3"
                elif name.startswith("raidz"):
                    return "raidz"
                return False

            def validate(self, level=0):
                for c in self:
                    c.validate(level+1)
                if level == 1:
                    if len(self.children) == 0:
                        stripe = self.parent.find_by_name("stripe")
                        if not stripe:
                            stripe = Tnode("stripe", self._doc)
                            stripe.type = 'stripe'
                            self.parent.append(stripe)
                        self.parent.children.remove(self)
                        stripe.append(self)
                        stripe.validate(level)
                    else:
                        self.type = self._vdev_type(self.name)
                elif level == 2:
                    # The parent of a leaf should be a vdev
                    if not self._is_vdev(self.parent.name) and \
                        self.parent.parent is not None:
                        raise Exception("Oh noes! This damn thing should be a vdev! %s" % self.parent)
                    search = self._doc.xpathEval("//class[name = 'LABEL']//provider[name = '%s']/../name" % self.name)
                    if len(search) > 0:
                        self.devname = search[0].content
                    else:
                        search = self._doc.xpathEval("//class[name = 'DEV']/geom[name = '%s']" % self.name)
                        if len(search) > 0:
                            self.devname = self.name
                        else:
                            raise Exception("It should be a valid device: %s" % self.name)

            def dump(self, level=0):
                if level == 2:
                    return self.devname
                if level == 1:
                    disks = []
                    for c in self:
                        disks.append(c.dump(level+1))
                    return {'disks': disks, 'type': self.type}
                if level == 0:
                    self.validate()
                    vdevs = []
                    for c in self:
                        vdevs.append(c.dump(level+1))
                    return {'name': self.name, 'vdevs': vdevs}

        for pool in RE_POOL_NAME.findall(res):
            # get status part of the pool
            status = res.split('pool: %s' % pool)[1].split('config:')[1].split('pool:')[0]
            roots = {'cache': None, 'logs': None, 'spares': None}
            lastident = None
            for line in status.split('\n'):
                if line.startswith('\t'):
                    spaces, word = re.search(r'^(?P<spaces>[ ]*)(?P<word>\S+)', line[1:]).groups()
                    ident = len(spaces) / 2
                    if ident == 0:
                        tree = Tnode(word, doc)
                        roots[word] = tree
                        pnode = tree
                    elif ident == lastident + 1:
                        node = Tnode(word, doc)
                        pnode.append(node)
                        pnode = node
                    elif ident == lastident:
                        node = Tnode(word, doc)
                        pnode.parent.append(node)
                    elif ident < lastident:
                        node = Tnode(word, doc)
                        tree.append(node)
                        pnode = node
                    lastident = ident

            volumes.append({
                'label': pool,
                'type': 'zfs',
                'group_type': 'none',
                'cache': roots['cache'].dump() if roots['cache'] else None,
                'logs': roots['logs'].dump() if roots['logs'] else None,
                'spare': roots['spares'].dump() if roots['spares'] else None,
                'disks': roots[pool].dump(),
                })

        return volumes

    def zfs_import(self, name):
        imp = self.__pipeopen('zpool import -R /mnt %s' % name)
        imp.wait()
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
        imp.wait()
        if imp.returncode == 0:
            return True
        return False

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
        self.__system("cp /data/factory-v1.db /data/freenas-v1.db")

    def config_upload(self, f):
        import sqlite3
        import tempfile
        sqlite = f.read()
        f = tempfile.NamedTemporaryFile()
        f.write(sqlite)
        f.flush()
        try:
            conn = sqlite3.connect(f.name)
            cur = conn.cursor()
            cur.execute("""SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name;""")
        except sqlite3.DatabaseError:
            f.close()
            return False
        else:
            db = open('/data/uploaded.db', 'w')
            db.write(sqlite)
            db.close()
            f.close()
            # Now we must run the migrate operation in the case the db is older
            self.__system("touch /data/need-update")
            return True

    def zfs_get_options(self, name):
        data = {}
        name = str(name)
        zfsproc = self.__pipeopen('zfs get -H -o value,source compression "%s"' % (name))
        fields = zfsproc.communicate()[0].split('\n')[0].split("\t")
        if fields[1] == "default":
            data['compression'] = "inherit"
        else:
            data['compression'] = fields[0]
        zfsproc = self.__pipeopen('zfs get -H -o value,source atime %s' % (name))
        fields = zfsproc.communicate()[0].split('\n')[0].split("\t")
        if fields[1] == "default":
            data['atime'] = "inherit"
        else:
            data['atime'] = fields[0]
        zfsproc = self.__pipeopen('zfs get -H -o value refquota %s' % (name))
        data['refquota'] = zfsproc.communicate()[0].split('\n')[0]
        zfsproc = self.__pipeopen('zfs get -H -o value quota %s' % (name))
        data['quota'] = zfsproc.communicate()[0].split('\n')[0]
        zfsproc = self.__pipeopen('zfs get -H -o value refreservation %s' % (name))
        data['refreservation'] = zfsproc.communicate()[0].split('\n')[0]
        zfsproc = self.__pipeopen('zfs get -H -o value reservation %s' % (name))
        data['reservation'] = zfsproc.communicate()[0].split('\n')[0]
        return data

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

    def geom_disk_state(self, geom, group_type, devname):
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

    def __geom_confxml(self):
        from libxml2 import parseDoc
        sysctl_proc = self.__pipeopen('sysctl -b kern.geom.confxml')
        return (parseDoc(sysctl_proc.communicate()[0][:-1]))

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

        elif tp == 'label':
            search = doc.xpathEval("//class[name = 'LABEL']/geom//provider[name = '%s']/../name" % value)
            if len(search) > 0:
                return search[0].content

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

def usage():
    print ("Usage: %s action command" % argv[0])
    print """\
    Action is one of:
        start: start a command
        stop: stop a command
        restart: restart a command
        reload: reload a command (try reload, if unsuccessful do restart)
        change: notify change for a command (try self.reload, if unsuccessful do start)"""
    exit

# When running as standard-alone script
if __name__ == '__main__':
    from sys import argv
    if len(argv) < 3:
        usage()
    else:
        n = notifier()
        try:
            f = getattr(n, argv[1])
        except:
            print ("Unknown action: %s" % argv[1])
            usage()
        print f(*argv[2:])
