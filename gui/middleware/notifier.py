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
from shlex import split as shlex_split
from subprocess import Popen, PIPE

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
        args = shlex_split(command)
        return Popen(args, stdin = PIPE, stdout = PIPE, stderr = PIPE, close_fds = True)

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
                    self.__system("/usr/sbin/service forcestop " + action)
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
        }
        if what in service2daemon:
            procname, pidfile = service2daemon[what]
            retval = self.__system_nolog("/bin/pgrep -F %s %s" % (pidfile, procname))
            if retval == 0:
                return True
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

    def restart(self, what):
        """ Restart the service specified by "what".

        The helper will use method self._restart_[what]() to restart the service.
        If the method does not exist, it would fallback using service(8)."""
        self._simplecmd("restart", what)

    def reload(self, what):
        """ Reload the service specified by "what".

        The helper will use method self._reload_[what]() to reload the service.
        If the method does not exist, the helper will try self.restart of the
        service instead."""
        try:
            self._simplecmd("reload", what)
        except:
            self.restart(what)

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
        self.__system("/usr/sbin/service hostname quietstart")
        self.__system("/usr/sbin/service routing restart")

    def _reload_timeservices(self):
        self.__system("/usr/sbin/service ix-localtime quietstart")
        self.__system("/usr/sbin/service ix-ntpd quietstart")
        self.__system("/usr/sbin/service ntpd restart")

    def _reload_ssh(self):
        self.__system("/usr/sbin/service ix-sshd quietstart")
        self.__system("/usr/sbin/service sshd restart")

    def _restart_ssh(self):
        self.__system("/usr/sbin/service ix-sshd quietstart")
        self.__system("/usr/sbin/service sshd restart")

    def _restart_ldap(self):
        self.__system("/usr/sbin/service ix-ldap quietstart")
        self.__system("/usr/sbin/service ix-nsswitch quietstart")
        self.__system("/usr/sbin/service ix-pam quietstart")
        self.__system("/usr/sbin/service ix-samba quietstart")
        self.__system("/usr/sbin/service samba forcestop")
        self.__system("/usr/bin/killall nmbd")
        self.__system("/usr/bin/killall smbd")
        self.__system("/usr/bin/killall winbindd")
        self.__system("/bin/sleep 5")
        self.__system("/usr/sbin/service samba quietstart")

    def _restart_activedirectory(self):
        self.__system("/usr/sbin/service ix-kerberos quietstart")
        self.__system("/usr/sbin/service ix-nsswitch quietstart")
        self.__system("/usr/sbin/service ix-pam quietstart")
        self.__system("/usr/sbin/service ix-samba quietstart")
        self.__system("/usr/sbin/service ix-kinit quietstart")
        self.__system("/usr/sbin/service ix-activedirectory quietstart")
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

    def _start_ftp(self):
        self.__system("/usr/sbin/service ix-proftpd quietstart")
        self.__system("/usr/sbin/service proftpd start")

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
        dbname = ""
        try:
            from freenasUI.settings import DATABASE_NAME as dbname
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
                      "| awk '{print ($3 / (1024*1024)) - 4;}'`" % (devname, devname))
        if label != "":
            self.__system("gpart create -s gpt /dev/%s && gpart add -b 128 -t freebsd-swap -l swap-%s -s %d %s && gpart add -t %s -l %s %s" %
                         (devname, label, swapsize, devname, type, label, devname))
        else:
            self.__system("gpart create -s gpt /dev/%s && gpart add -t freebsd-swap -l swap-%s -s %d %s && gpart add -t %s %s" %
                         (devname, devname, swapsize, devname, type, devname))
        return need4khack

    def __gpt_unlabeldisk(self, devname):
        """Unlabel the disk"""
        self.__system("swapoff /dev/gpt/swap-%s" % devname)
        self.__system("gpart destroy -F /dev/%s" % devname)

        # To be safe, wipe out the disk, both ends...
        # TODO: This should be fixed, it's an overkill to overwrite that much
        self.__system("dd if=/dev/zero of=/dev/%s bs=1m count=10" % (devname))
        self.__system("dd if=/dev/zero of=/dev/%s bs=1m oseek=`diskinfo %s "
                      "| awk '{print int($3 / (1024*1024)) - 3;}'`" % (devname, devname))

    def __create_zfs_volume(self, c, z_id, z_name, swapsize):
        """Internal procedure to create a ZFS volume identified by volume id"""
        z_vdev = ""
        need4khack = False
        # Grab all disk groups' id matching the volume ID
        c.execute("SELECT id, group_type FROM storage_diskgroup WHERE "
                  "group_volume_id = ?", (z_id,))
        vgroup_list = c.fetchall()
        self.__system("swapoff -a")
        for vgrp_row in vgroup_list:
            hack_vdevs = []
            vgrp = (vgrp_row[0],)
            vgrp_type = vgrp_row[1]
            if vgrp_type != 'stripe':
                z_vdev += " " + vgrp_type
            # Grab all member disks from the current vdev group
            c.execute("SELECT disk_disks, disk_name FROM storage_disk WHERE "
                      "disk_group_id = ?", vgrp)
            vdev_member_list = c.fetchall()
            for disk in vdev_member_list:
                need4khack = self.__gpt_labeldisk(type = "freebsd-zfs",
                                                  devname = disk[0],
                                                  label = disk[1],
                                                  swapsize=swapsize)
                if need4khack:
                    hack_vdevs.append(disk[1])
                    self.__system("gnop create -S 4096 /dev/gpt/" + disk[1])
                    z_vdev += " /dev/gpt/" + disk[1] + ".nop"
                else:
                    z_vdev += " /dev/gpt/" + disk[1]
        self._reload_disk()
        # Finally, create the zpool.
        # TODO: disallowing cachefile may cause problem if there is
        # preexisting zpool having the exact same name.
        if not os.path.isdir("/data/zfs"):
            os.makedirs("/data/zfs")
        self.__system("zpool create -o cachefile=/data/zfs/zpool.cache "
                      "-fm /mnt/%s %s %s" % (z_name, z_name, z_vdev))
        # If we have 4k hack then restore system to whatever it should be
        if need4khack:
            self.__system("zpool export %s" % (z_name))
            for disk in hack_vdevs:
                self.__system("gnop destroy /dev/gpt/" + disk + ".nop")
            self.__system("zpool import %s" % (z_name))

    # TODO: This is a rather ugly hack and duplicates some code, need to
    # TODO: cleanup this with the __create_zfs_volume.
    def zfs_volume_attach_group(self, group_id):
        """Attach a disk group to a zfs volume"""
        c = self.__open_db()
        c.execute("SELECT adv_swapondrive FROM system_advanced ORDER BY -id LIMIT 1")
        swapsize=c.fetchone()[0]


        c.execute("SELECT id, group_type, group_volume_id FROM storage_diskgroup WHERE "
                  "id = ?", (group_id))
        vgroup_list = c.fetchall()
        volume_id = vgroup_list[0][2]

        c.execute("SELECT vol_fstype, vol_name FROM storage_volume WHERE id = ?",
                 (volume_id,))
        volume = c.fetchone()
        assert volume[0] == 'ZFS'
        z_name = volume[1]

        z_vdev = ""
        need4khack = False
        # Grab all disk groups' id matching the volume ID
        self.__system("swapoff -a")
        for vgrp_row in vgroup_list:
            hack_vdevs = []
            vgrp = (vgrp_row[0],)
            vgrp_type = vgrp_row[1]
            if vgrp_type != 'stripe':
                z_vdev += " " + vgrp_type
            # Grab all member disks from the current vdev group
            c.execute("SELECT disk_disks, disk_name FROM storage_disk WHERE "
                      "disk_group_id = ?", vgrp)
            vdev_member_list = c.fetchall()
            for disk in vdev_member_list:
                need4khack = self.__gpt_labeldisk(type = "freebsd-zfs",
                                                  devname = disk[0],
                                                  label = disk[1],
                                                  swapsize=swapsize)
                if need4khack:
                    hack_vdevs.append(disk[1])
                    self.__system("gnop create -S 4096 /dev/gpt/" + disk[1])
                    z_vdev += " /dev/gpt/" + disk[1] + ".nop"
                else:
                    z_vdev += " /dev/gpt/" + disk[1]
        self._reload_disk()
        # Finally, attach new groups to the zpool.
        self.__system("zpool add %s %s" % (z_name, z_vdev))

    def create_zfs_dataset(self, path, props=None):
        """Internal procedure to create ZFS volume"""
        options = " "
        if props:
            assert type(props) is types.DictType
            for k in props.keys():
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
        zfsproc = self.__pipeopen("zfs destroy %s" % (path))
        retval = zfsproc.communicate()[1]
        return retval

    def __destroy_zfs_volume(self, c, z_id, z_name):
        """Internal procedure to destroy a ZFS volume identified by volume id"""
        # First, destroy the zpool.
        self.__system("zpool destroy -f %s" % (z_name))

        # Clear out disks associated with the volume
        c.execute("SELECT id FROM storage_diskgroup WHERE group_volume_id = ?", (z_id,))
        vgroup_list = c.fetchall()
        for vgrp in vgroup_list:
            c.execute("SELECT disk_disks, disk_name FROM storage_disk WHERE "
                      "disk_group_id = ?", vgrp)
            vdev_member_list = c.fetchall()
            for disk in vdev_member_list:
                self.__gpt_unlabeldisk(devname = disk[0])
        self._reload_disk()

    def __create_ufs_volume(self, c, u_id, u_name, swapsize):
        geom_vdev = ""
        ufs_device = ""
        c.execute("SELECT id, group_type, group_name FROM storage_diskgroup "
                  "WHERE group_volume_id = ?", (u_id,))
        # TODO: We do not support multiple GEOM levels for now.
        vgrp_row = c.fetchone()
        ufs_volume_id = (vgrp_row[0],)
        geom_type = vgrp_row[1]
        geom_name = vgrp_row[2]
        # Grab all disks from the group
        c.execute("SELECT disk_disks, disk_name FROM storage_disk WHERE "
                  "disk_group_id = ?", ufs_volume_id)
        if geom_type == '':
            disk = c.fetchone()
            self.__gpt_labeldisk(type = "freebsd-ufs", devname = disk[0], swapsize=swapsize)
            ufs_device = "/dev/ufs/" + disk[1]
            # TODO: Need to investigate why /dev/gpt/foo can't have label /dev/ufs/bar
            # generated automatically
            self.__system("newfs -U -L %s /dev/%sp2" % (u_name, disk[0]))
        else:
            vdev_member_list = c.fetchall()
            for disk in vdev_member_list:
                geom_vdev += " /dev/" + disk[0]
            self.__system("geom %s load" % (geom_type))
            self.__system("geom %s label %s %s" % (geom_type, geom_name, geom_vdev))
            ufs_device = "/dev/%s/%s" % (geom_type, geom_name)
            self.__system("newfs -U -L %s %s" % (u_name, ufs_device))

    def __destroy_ufs_volume(self, c, u_id, u_name):
        """Internal procedure to destroy a UFS volume identified by volume id"""
        c.execute("SELECT id, group_type, group_name FROM storage_diskgroup WHERE "
                  "group_volume_id = ?", (u_id,))
        vgrp_row = c.fetchone()
        ufs_volume_id = (vgrp_row[0],)
        geom_type = vgrp_row[1]
        geom_name = vgrp_row[2]
        # Grab all disks from the group
        c.execute("SELECT disk_disks, disk_name FROM storage_disk WHERE "
                  "disk_group_id = ?", ufs_volume_id)
        if geom_type == '':
            disk = c.fetchone()
            self.__system("umount -f /dev/ufs/" + u_name)
            self.__gpt_unlabeldisk(devname = disk[0])
        else:
            self.__system("swapoff -a")
            self.__system("umount -f /dev/ufs/" + u_name)
            self.__system("geom %s stop %s" % (geom_type, geom_name))
            vdev_member_list = c.fetchall()
            for disk in vdev_member_list:
                disk_name = " /dev/" + disk[0]
                self.__system("geom %s clear %s" % (geom_type, disk_name))
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (disk[0]))
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m oseek=`diskinfo %s "
                      "| awk '{print ($3 / (1024*1024)) - 4;}'`" % (disk[0], disk[0]))
        self._reload_disk()

    def _init_volume(self, volume_id, *args, **kwargs):
        """Initialize a volume designated by volume_id"""
        c = self.__open_db()
        c.execute("SELECT adv_swapondrive FROM system_advanced ORDER BY -id LIMIT 1")
        swapsize=c.fetchone()[0]
        c.execute("SELECT vol_fstype, vol_name FROM storage_volume WHERE id = ?",
                 (volume_id,))
        volume = c.fetchone()

        assert volume[0] == 'ZFS' or volume[0] == 'UFS'
        if volume[0] == 'ZFS':
            if kwargs.pop('add', False) == True:
                #TODO __add_zfs_volume
                #self.__add_zfs_volume(c, volume_id, volume[1], swapsize)
                pass
            else:
                self.__create_zfs_volume(c, volume_id, volume[1], swapsize)
        elif volume[0] == 'UFS':
            self.__create_ufs_volume(c, volume_id, volume[1], swapsize)
        self._reload_disk()

    def _init_zfs_disk(self, disk_id):
        """Initialize a disk designated by disk_id"""
        """notifier().init("disk", 1)"""
        c = self.__open_db()
        c.execute("SELECT adv_swapondrive FROM system_advanced ORDER BY -id LIMIT 1")
        swapsize=c.fetchone()[0]
        c.execute("SELECT disk_disks, disk_name FROM storage_disk WHERE id = ?", disk_id)
        disk = c.fetchone()
        self.__gpt_labeldisk(type = "freebsd-zfs", devname = disk[0],
                             label = disk[1], swapsize=swapsize)

    def zfs_replace_disk(self, volume_id, from_diskid, to_diskid):
        """Replace disk in volume_id from from_diskid to to_diskid"""
        """Gather information"""
        c = self.__open_db()
        c.execute("SELECT adv_swapondrive FROM system_advanced ORDER BY -id LIMIT 1")
        swapsize=c.fetchone()[0]

        c.execute("SELECT vol_fstype, vol_name FROM storage_volume WHERE id = ?",
                 (volume_id,))
        volume = c.fetchone()
        assert volume[0] == 'ZFS'

        # TODO: Test on real hardware to see if ashift would persist across replace
        volume = volume[1]
        c.execute("SELECT disk_name FROM storage_disk WHERE id = ?", from_diskid)
        fromdev_label = c.fetchone()[0]
        fromdev = 'gpt/' + fromdev_label
        fromdev_swap = '/dev/gpt/swap-' + fromdev_label
        c.execute("SELECT disk_disks, disk_name FROM storage_disk WHERE id = ?", to_diskid)
        disk = c.fetchone()
        devname = disk[0]
        label = disk[1]
        todev = 'gpt/' + label
        todev_swap = '/dev/gpt/swap-' + label

        self.__system('/sbin/swapoff %s' % (fromdev_swap))

        if from_diskid == to_diskid:
            self.__system('/sbin/zpool offline %s %s' % (volume, fromdev))

        self.__gpt_labeldisk(type = "freebsd-zfs", devname = devname,
                             label = label, swapsize=swapsize)

        self.__system('/sbin/swapon %s' % (todev_swap))

        if from_diskid == to_diskid:
            self.__system('/sbin/zpool online %s %s' % (volume, fromdev))
            ret = self.__system_nolog('/sbin/zpool replace %s %s' % (volume, fromdev))
            if ret == 256:
                ret = self.__system_nolog('/sbin/zpool scrub %s' % (volume))
        else:
            ret = self.__system_nolog('/sbin/zpool replace %s %s %s' % (volume, fromdev, todev))
        return ret

    def zfs_detach_disk(self, volume_id, disk_id):
        """Detach a disk from zpool
           (more technically speaking, a replaced disk.  The replacement actually
           creates a mirror for the device to be replaced)"""
        c = self.__open_db()

        c.execute("SELECT vol_fstype, vol_name FROM storage_volume WHERE id = ?",
                 (volume_id,))
        volume = c.fetchone()
        assert volume[0] == 'ZFS'

        # TODO: Handle with 4khack aftermath
        volume = volume[1]
        c.execute("SELECT disk_name FROM storage_disk WHERE id = ?", disk_id)
        label = c.fetchone()[0]
        devname = 'gpt/' + label

        # Remove the swap partition for another time to be sure.
        # TODO: swap partition should be trashed instead.
        devname_swap = '/dev/gpt/swap-' + label
        self.__system('/sbin/swapoff %s' % (devname_swap))

        ret = self.__system_nolog('/sbin/zpool detach %s %s' % (volume, devname))
        # TODO: This operation will cause damage to disk data which should be limited
        self.__gpt_unlabeldisk(label)
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
        c.execute("SELECT disk_name FROM storage_disk WHERE id = ?", disk_id)
        devname = 'gpt/' + c.fetchone()[0]

        ret = self.__system_nolog('/sbin/zpool add %s spare %s' % (volume, devname))
        return ret

    def _destroy_volume(self, volume_id):
        """Destroy a volume designated by volume_id"""
        c = self.__open_db()
        c.execute("SELECT vol_fstype, vol_name FROM storage_volume WHERE id = ?",
                 (volume_id,))
        volume = c.fetchone()

        assert volume[0] in ('ZFS', 'UFS', 'iscsi', 'NTFS', 'MSDOSFS')
        if volume[0] == 'ZFS':
            self.__destroy_zfs_volume(c = c, z_id = volume_id, z_name = volume[1])
        elif volume[0] == 'UFS':
            self.__destroy_ufs_volume(c = c, u_id = volume_id, u_name = volume[1])

    def _reload_disk(self):
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
        self.reload("cifs")

    def mp_change_permission(self, path='/mnt', user='root', group='wheel',
                             mode='0755', recursive=False):
        if recursive:
            flags='-R '
        else:
            flags=''
        self.__system("/usr/sbin/chown %s'%s':'%s' %s" % (flags, user, group, path))
        self.__system("/bin/chmod %s%s %s" % (flags, mode, path))

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

    def get_volume_status(self, name, fs, group_type):
        if fs == 'ZFS':
            result = self.__pipeopen('zpool list -H -o health %s' % name.__str__()).communicate()[0].strip('\n')
            return result
        elif fs == 'UFS':
            gtype = None
            for gtypes in group_type:
                if 'mirror' == gtypes[0]:
                    gtype = 'mirror'
                    break
                elif 'stripe' == gtypes[0]:
                    gtype = 'stripe'
                    break
                elif 'raid3' == gtypes[0]:
                    gtype = 'raid3'
                    break

            if gtype == 'mirror':
                p1 = self.__pipeopen('gmirror list')
            if gtype == 'stripe':
                p1 = self.__pipeopen('gstripe list')
            if gtype == 'raid3':
                p1 = self.__pipeopen('graid3 list')

            if gtype:
                p2 = Popen(["grep", "name: %s%s" % (name, gtype), "-A", "1"], stdin=p1.stdout, stdout=PIPE)
                p3 = Popen(["grep", "State:"], stdin=p2.stdout, stdout=PIPE)
                p1.wait()
                p2.wait()
                p3.wait()
                output = p3.communicate()[0]
                return output.split(' ')[1]
            else:
                return 'ONLINE'
        else:
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

    def get_partitions(self):
        disks = self.get_disks().keys()
        partitions = {}
        for disk in disks:

            listing = glob.glob('/dev/%s[a-fps]*' % disk)
            listing.sort()
            for part in list(listing):
                toremove = len([i for i in listing if i.startswith(part) and i != part]) > 0
                if toremove:
                    listing.remove(part)

            for part in listing:
                p1 = Popen(["/usr/sbin/diskinfo", part], stdin=PIPE, stdout=PIPE)
                p1.wait()
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
            p1 = Popen(["fsck_ufs", "-p", dev], stdin=PIPE, stdout=PIPE)
            p1.wait()
            if p1.returncode == 0:
                return True
        elif fstype == 'NTFS':
            p1 = Popen(["ntfsfix", dev], stdin=PIPE, stdout=PIPE)
            p1.wait()
            if p1.returncode == 0:
                return True
        elif fstype == 'MSDOSFS':
            p1 = Popen(["fsck_msdosfs", "-p", dev], stdin=PIPE, stdout=PIPE)
            p1.wait()
            if p1.returncode == 0:
                return True

        return False

    def label_disk(self, label, dev, fstype):
        """
        Label the disk being manually imported
        Currently UFS, NTFS and MSDOSFS are supported
        """

        if fstype == 'UFS':
            p1 = Popen(["tunefs", "-L", label, dev], stdin=PIPE, stdout=PIPE)
            p1.wait()
            if p1.returncode == 0:
                return True
        elif fstype == 'NTFS':
            p1 = Popen(["ntfslabel", dev, label], stdin=PIPE, stdout=PIPE)
            p1.wait()
            if p1.returncode == 0:
                return True
        elif fstype == 'MSDOSFS':
            p1 = Popen(["mlabel", "-i", dev, "::%s" % label], stdin=PIPE, stdout=PIPE)
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
        # Detect GEOM mirror, stripe and raid3
        RE_GEOM_NAME = re.compile(r'^Geom name: (?P<name>\w+)', re.I)
        RE_DEV_NAME = re.compile(r'Name: (?P<name>\w+)', re.I)
        for geom in ('mirror', 'stripe', 'raid3'):
            p1 = Popen(["geom", geom, "list"], stdin=PIPE, stdout=PIPE)
            p1.wait()
            if p1.returncode == 0:
                res = p1.communicate()[0]
                for item in res.split('\n\n')[:-1]:
                    search = RE_GEOM_NAME.search(item)
                    if search:
                        label = search.group("name")
                        label = label.replace(geom, '')
                        consumers = item.split('Consumers:')[1]
                        if RE_DEV_NAME.search(consumers):
                            disks = []
                            for search in RE_DEV_NAME.finditer(consumers):
                                disks.append(search.group("name"))
                            volumes.append({
                                'label': label,
                                'type': 'geom',
                                'group_type': geom,
                                'disks': disks,
                                })

        RE_POOL_NAME = re.compile(r'pool: (?P<name>\w+)', re.I)
        RE_DISK = re.compile(r'(?P<disk>[a-d]{2}\d+)[a-fsp]')
        p1 = Popen(["zpool", "import"], stdin=PIPE, stdout=PIPE)
        p1.wait()
        if p1.returncode == 0:
            res = p1.communicate()[0]
            if RE_POOL_NAME.search(res):
                label = RE_POOL_NAME.search(res).group("name")
                status = res.split('pool: %s' % label)[1].split('config:')[1].split('pool:')[0]
                if status.find("mirror") >= 0:
                    group_type = 'mirror'
                elif status.find("raidz1") >= 0:
                    group_type = 'raidz1'
                elif status.find("raidz2") >= 0:
                    group_type = 'raidz2'
                else:
                    group_type = 'stripe'

                disks = []
                logs = []
                cache = []
                spare = []
                section = None # None, log, cache or spare
                for line in status.split('\n'):
                    if re.compile('^$').search(line) or not line.startswith('\t  '):
                        if line.startswith('\tlogs'):
                            section = 'logs'
                        if line.startswith('\tcache'):
                            section = 'cache'
                        if line.startswith('\tspare'):
                            section = 'spare'
                        continue
                    line = line.strip('\t').strip(' ')
                    name = line.split(' ')[0]
                    p1 = Popen(["geom", "label", "status", "-s"], stdin=PIPE, stdout=PIPE)
                    p2 = Popen(["tr", "-s", " "], stdin=p1.stdout, stdout=PIPE)
                    p3 = Popen(["sed", "-e", "s/^[ \t]//g"], stdin=p2.stdout, stdout=PIPE)
                    p4 = Popen(["grep", "^%s" % name], stdin=p3.stdout, stdout=PIPE)
                    p1.wait()
                    p2.wait()
                    p3.wait()
                    p4.wait()
                    if p4.returncode == 0:
                        disk = p4.communicate()[0].split(' ')[2].split('\n')[0]
                    else:
                        disk = name
                    if RE_DISK.search(disk):
                        disk = RE_DISK.search(disk).group("disk")
                    if disk in ('mirror', 'raidz1', 'raidz2'):
                        continue

                    if section == 'logs':
                        logs.append(disk)
                    elif section == 'cache':
                        cache.append(disk)
                    elif section == 'spare':
                        spare.append(disk)
                    else:
                        disks.append(disk)

                volumes.append({
                    'label': label,
                    'type': 'zfs',
                    'group_type': group_type,
                    'cache': cache,
                    'logs': logs,
                    'spare': spare,
                    'disks': disks,
                    })

        return volumes
            
    def zfs_import(self, name):
        imp = self.__pipeopen('zpool import %s' % name)
        imp.wait()
        if imp.returncode == 0:
            return True
        return False

    def zfs_snapshot_list(self):
        fsinfo = dict()

        zfsproc = self.__pipeopen("/sbin/zfs list -t snapshot -H")
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
                except:
                    snaplist = []
                snaplist.append(dict([('fullname', snapname), ('name', name), ('used', used), ('refer', refer)]))
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

    def zfs_inherit_option(self, name, item):
        name = str(name)
        item = str(item)
        zfsproc = self.__pipeopen('zfs inherit %s "%s"' % (item, name))
        zfsproc.wait()
        print zfsproc.returncode
        if zfsproc.returncode == 0:
            return True
        return False

    def geom_disk_state(self, geom, group_type, devname):
        p1 = self.__pipeopen("geom %s list %s" % (str(group_type), str(geom)))
        output = p1.communicate()[0]
        reg = re.search(r'^\d\. Name: %s.*?State: (?P<state>\w+)' % devname, output, re.S|re.I|re.M)
        if reg:
            return reg.group("state")
        else:
            return "FAILED"

    def geom_disk_replace(self, volume_id, from_diskid, to_diskid):
        """Replace disk in volume_id from from_diskid to to_diskid"""
        """Gather information"""

        c = self.__open_db()
        c.execute("SELECT vol_fstype, vol_name FROM storage_volume WHERE id = ?",
                 (volume_id,))
        volume = c.fetchone()
        assert volume[0] == 'UFS'
        volume = volume[1]
        c.execute("SELECT disk_group_id FROM storage_disk WHERE id = ?", from_diskid)
        dg_id = c.fetchone()[0]

        c.execute("SELECT disk_name FROM storage_disk WHERE id = ?", to_diskid)
        todev = c.fetchone()[0]

        c.execute("SELECT group_name, group_type FROM storage_diskgroup WHERE id = ?", str(dg_id))
        dg = c.fetchone()
        group_name = dg[0]
        group_type = dg[1]

        if group_type == "mirror":
            rv = self.__system_nolog("geom mirror forget %s" % (str(group_name),))
            if rv != 0:
                return rv
            rv = self.__system_nolog("geom mirror insert %s /dev/%s" % (str(group_name), str(todev),))
            return rv

        elif group_type == "raid3":
            p1 = self.__pipeopen("geom raid3 list %s" % str(group_name))
            p1.wait()
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

    def zfs_sync_datasets(self, vol_id):
        c, conn = self.__open_db(True)
        c.execute("SELECT vol_name FROM storage_volume WHERE id = ?", (vol_id,))
        vol_name = c.fetchone()[0]
        c.execute("SELECT mp_path FROM storage_mountpoint WHERE mp_volume_id = ?", (vol_id,))
        mp_path = c.fetchone()[0]

        c.execute("DELETE FROM storage_mountpoint WHERE mp_ischild = 1 AND mp_volume_id = %s" % str(vol_id))

        p1 = self.__pipeopen("zfs list -t filesystem -o name -H -r %s" % str(vol_name))
        p1.wait()
        ret = p1.communicate()[0].split('\n')[1:-1]
        for dataset in ret:
            name = "".join(dataset.split('/')[1:])
            mp = os.path.join(mp_path, name)
            c.execute("INSERT INTO storage_mountpoint (mp_volume_id, mp_path, mp_options, mp_ischild) VALUES (?, ?, ?, ?)", (vol_id, mp,"noauto","1"), )
            self.__system_nolog("zfs set mountpoint=%s %s" % (str(mp), str(dataset)) )
        conn.commit()
        c.close()

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
    if len(argv) != 3:
        usage()
    else:
        n = notifier()
        try:
            f = getattr(n, argv[1])
        except:
            print ("Unknown action: %s" % argv[1])
            usage()
        f(argv[2])
