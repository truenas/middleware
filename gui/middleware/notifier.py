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
import syslog
from pwd import getpwnam as ___getpwnam
from shlex import split as shlex_split
from subprocess import Popen, PIPE as ___PIPE

class notifier:
	from os import system as ___system
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
	def __pipeopen(self, command):
		syslog.openlog("freenas", syslog.LOG_CONS | syslog.LOG_PID)
		syslog.syslog(syslog.LOG_NOTICE, "Popen()ing: " + command)
		args = shlex_split(command)
		return Popen(args, stdin = ___PIPE, stdout = ___PIPE, stderr = ___PIPE, close_fds = True)
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
				self.__system("/usr/sbin/service " + what + " " + action)
				f = self._do_nada
			else:
				raise "Internal error: Unknown command"
		try:
			f()
		except:
			raise
	def init(self, what, objectid = None):
		""" Dedicated command to create "what" designated by an optional objectid.
		
		The helper will use method self._init_[what]() to create the object"""
		if objectid == None:
			self._simplecmd("init", what)
		else:
			try:
				f = getattr(self, '_init_' + what)
				f(objectid)
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
		If the method does not exist, the helper will try self.restart the service instead."""
		try:
			self._simplecmd("reload", what)
		except:
			self.restart(what)
	def change(self, what):
		""" Notify the service specified by "what" about a change.
		
		The helper will use method self.reload(what) to reload the service.
		If the method does not exist, the helper will try self.start the service instead."""
		try:
			self.reload(what)
		except:
			self.start(what)
	def _start_network(self):
		# TODO: Skip this step when IPv6 is already enabled
		self.__system("/sbin/sysctl net.inet6.ip6.auto_linklocal=1")
		self.__system("/usr/sbin/service autolink auto_linklocal quietsatrt")
		self.__system("/usr/sbin/service netif stop")
		self.__system("/etc/netstart")
	def _reload_named(self):
		self.__system("/usr/sbin/service named reload")
	def _reload_networkgeneral(self):
		self.__system("/bin/hostname \"\"")
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
	def _reload_tftp(self):
		self.__system("/usr/sbin/service ix-inetd quietstart")
		self.__system("/usr/sbin/service inetd restart")
	def _restart_tftp(self):
		self.__system("/usr/sbin/service ix-inetd quietstart")
		self.__system("/usr/sbin/service inetd restart")
	def _reload_ftp(self):
		self.__system("/usr/sbin/service ix-proftpd quietstart")
		self.__system("/usr/sbin/service proftpd restart")
        def _load_afp(self):
                self.__system("/usr/sbin/service ix-afpd quietstart")
                self.__system("/usr/sbin/service netatalk quietstart")
        def _restart_afp(self):
                self.__system("/usr/sbin/service ix-afpd quietstart")
                self.__system("/usr/sbin/service netatalk restart")
	def _reload_nfs(self):
		self.__system("/usr/sbin/service ix-nfsd quietstart")
		self.__system("/usr/sbin/service mountd forcerestart")
	def _restart_nfs(self):
		self.__system("/usr/sbin/service mountd forcestop")
		self.__system("/usr/sbin/service nfsd forcestop")
		self.__system("/usr/sbin/service ix-nfsd quietstart")
		self.__system("/usr/sbin/service nfsd quietstart")
	def _restart_system(self):
		self.__system("/bin/sleep 3 && /sbin/shutdown -r now &")
	def _stop_system(self):
		self.__system("/sbin/shutdown -p now")
	def _reload_cifs(self):
		self.__system("/usr/sbin/service ix-samba quietstart")
		self.__system("/usr/sbin/service samba restart")
	def _restart_cifs(self):
		# TODO: bug in samba rc.d script
		# self.__system("/usr/sbin/service samba forcestop")
		self.__system("/usr/bin/killall nmbd")
		self.__system("/usr/bin/killall smbd")
		self.__system("/usr/sbin/service samba quietstart")
	def _restart_snmp(self):
		self.__system("/usr/sbin/service bsnmpd forcestop")
		self.__system("/usr/sbin/service bsnmpd quietstart")
        def __open_db(self):
                """Open and return a cursor object for database access."""
		dbname = ""
		try:
                	from freenasUI.settings import DATABASE_NAME as dbname
		except:
			dbname = '/data/freenas-v1.db'
                import sqlite3
                
                conn = sqlite3.connect(dbname)
                c = conn.cursor()
                return c
	def __gpt_labeldisk(self, type, devname, label = ""):
                """Label the whole disk with GPT under the desired label and type"""
                # To be safe, wipe out the disk, both ends... before we start
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m count=1" % (devname))
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m oseek=`diskinfo %s | awk '{print ($3 / (1024*1024)) - 3;}'`" % (devname, devname))
                # TODO: Support for 4k sectors (requires 8.1-STABLE after 213467).
		if label != "":
			self.__system("gpart create -s gpt /dev/%s && gpart add -t %s -l %s %s" % (devname, type, label, devname))
		else:
			self.__system("gpart create -s gpt /dev/%s && gpart add -t %s %s" % (devname, type, devname))
	def __gpt_unlabeldisk(self, devname):
		"""Unlabel the disk"""
		self.__system("gpart delete -i 1 /dev/%s && gpart destroy /dev/%s" % (devname, devname))
                # To be safe, wipe out the disk, both ends...
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m count=10" % (devname))
                self.__system("dd if=/dev/zero of=/dev/%s bs=1m oseek=`diskinfo %s | awk '{print ($3 / (1024*1024)) - 3;}'`" % (devname, devname))
        def __create_zfs_volume(self, c, z_id, z_name):
                """Internal procedure to create a ZFS volume identified by volume id"""
                z_vdev = ""
                # Grab all disk groups' id matching the volume ID
                c.execute("SELECT id, group_type FROM storage_diskgroup WHERE group_volume_id = ?", (z_id,))
		vgroup_list = c.fetchall()
		for vgrp_row in vgroup_list:
			vgrp = (vgrp_row[0],)
			vgrp_type = vgrp_row[1]
                        if vgrp_type != 'stripe':
			    z_vdev += " " + vgrp_type
			# Grab all member disks from the current vdev group
			c.execute("SELECT disk_disks, disk_name FROM storage_disk WHERE disk_group_id = ?", vgrp)
			vdev_member_list = c.fetchall()
			for disk in vdev_member_list:
				self.__gpt_labeldisk(type = "freebsd-zfs", devname = disk[0], label = disk[1])
				z_vdev += " /dev/gpt/" + disk[1]
		# Finally, create the zpool.
		self.__system("zpool create -fm /mnt/%s %s %s" % (z_name, z_name, z_vdev))
        def __destroy_zfs_volume(self, c, z_id, z_name):
		"""Internal procedure to destroy a ZFS volume identified by volume id"""
		# First, destroy the zpool.
		self.__system("zpool destroy -f %s" % (z_name))

		# Clear out disks associated with the volume
                c.execute("SELECT id FROM storage_diskgroup WHERE group_volume_id = ?", (z_id,))
		vgroup_list = c.fetchall()
		for vgrp in vgroup_list:
			c.execute("SELECT disk_disks, disk_name FROM storage_disk WHERE disk_group_id = ?", vgrp)
			vdev_member_list = c.fetchall()
			for disk in vdev_member_list:
				self.__gpt_unlabeldisk(devname = disk[0])
        def __create_ufs_volume(self, c, u_id, u_name):
                geom_vdev = ""
		ufs_device = ""
                c.execute("SELECT id, group_type, group_name FROM storage_diskgroup WHERE group_volume_id = ?", (u_id,))
		# TODO: We do not support multiple GEOM levels for now.
		vgrp_row = c.fetchone()
		ufs_volume_id = (vgrp_row[0],)
		geom_type = vgrp_row[1]
		geom_name = vgrp_row[2]
                # Grab all disks from the group
		c.execute("SELECT disk_disks, disk_name FROM storage_disk WHERE disk_group_id = ?", ufs_volume_id)
		if geom_type == '':
			disk = c.fetchone()
			self.__gpt_labeldisk(type = "freebsd-ufs", devname = disk[0])
			ufs_device = "/dev/ufs/" + disk[1]
			# TODO: Need to investigate why /dev/gpt/foo can't have label /dev/ufs/bar generated automatically
			self.__system("newfs -U -L %s /dev/%sp1" % (u_name, disk[0]))
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
                c.execute("SELECT id, group_type, group_name FROM storage_diskgroup WHERE group_volume_id = ?", (u_id,))
		vgrp_row = c.fetchone()
		ufs_volume_id = (vgrp_row[0],)
		geom_type = vgrp_row[1]
		geom_name = vgrp_row[2]
                # Grab all disks from the group
		c.execute("SELECT disk_disks, disk_name FROM storage_disk WHERE disk_group_id = ?", ufs_volume_id)
		if geom_type == '':
			disk = c.fetchone()
			self.__system("umount -f /dev/ufs/" + u_name)
			self.__gpt_unlabeldisk(devname = disk[0])
		else:
			self.__system("umount -f /dev/ufs/" + u_name)
			self.__system("geom %s stop %s" % (geom_type, geom_name))
			vdev_member_list = c.fetchall()
			for disk in vdev_member_list:
				disk_name = " /dev/" + disk[0]
				self.__system("geom %s clear %s" % (geom_type, disk_name))

        def _init_volume(self, volume_id):
		"""Initialize a volume designated by volume_id"""
                c = self.__open_db()
		c.execute("SELECT vol_fstype, vol_name FROM storage_volume WHERE id = ?", (volume_id,))
		volume = c.fetchone()

		if volume[0] == 'ZFS':
			# zfs creation needs write access to /boot/zfs.
			self.__system("/sbin/mount -uw /")
			self.__create_zfs_volume(c, volume_id, volume[1])
			self.__system("/sbin/mount -ur /")
		else:
			self.__create_ufs_volume(c, volume_id, volume[1])
		self._reload_disk()
        def _destroy_volume(self, volume_id):
		"""Initialize a volume designated by volume_id"""
                c = self.__open_db()
		c.execute("SELECT vol_fstype, vol_name FROM storage_volume WHERE id = ?", (volume_id,))
		volume = c.fetchone()

		if volume[0] == 'ZFS':
			self.__system("/sbin/mount -uw /")
        		self.__destroy_zfs_volume(c = c, z_id = volume_id, z_name = volume[1])
			self.__system("/sbin/mount -ur /")
                elif volume[0] == 'UFS':
			self.__destroy_ufs_volume(c = c, u_id = volume_id, u_name = volume[1])
        def _init_allvolumes(self):
                c = self.__open_db()
                # Create ZFS pools
                c.execute("SELECT id, vol_name FROM storage_volume WHERE vol_fstype = 'ZFS'")
                zfs_list = c.fetchall()
		if len(zfs_list) > 0:
			# We have to be able to write /boot/zfs and / to create mount points.
			self.__system("/sbin/mount -uw /")
			for row in zfs_list:
				z_id, z_name = row
				self.__create_zfs_volume(c = c, z_id = z_id, z_name = z_name)
			self.__system("/sbin/mount -ur /")
                # Create UFS file system and newfs
                c.execute("SELECT id, vol_name FROM storage_volume WHERE vol_fstype = 'UFS'")
	        ufs_list = c.fetchall()
		if len(ufs_list) > 0:
			for row in ufs_list:
				u_id, u_name = row
				self.__create_ufs_volume(c = c, u_id = u_id, u_name = u_name)
		self._reload_disk()
        def _reload_disk(self):
		self.__system("/usr/sbin/service ix-fstab quietstart")
		self.__system("/usr/sbin/service mountlate quietstart")
	# Create a user in system then samba
	def __pw_with_password(self, command, password):
		pw = self.__pipeopen(command)
		msg = pw.communicate("%s\n" % password)[1]
		if msg != "":
			syslog.syslog(syslog.LOG_NOTICE, "Command reports " + msg)
	def __smbpasswd(self, username, password):
		command = "/usr/local/bin/smbpasswd -s -a \"%s\"" % (username)
		smbpasswd = self.__pipeopen(command)
		smbpasswd.communicate("%s\n%s\n" % (password, password))
	def __issue_pwdchange(self, username, command, password):
		self.__pw_with_password(command, password)
		self.__smbpasswd(username, password)
	def user_create(self, username, fullname, password, uid = -1, gid = -1, shell = "/sbin/nologin", homedir = "/mnt"):
		"""Creates a user with the given parameters.
		uid and gid can be omitted or specified as -1 which means the system should
		choose automatically.

		The default shell is /sbin/nologin.

		Returns user uid and gid"""
		command = "/usr/sbin/pw useradd \"%s\" -h 0 -c \"%s\"" % (username, fullname)
		if uid >= 0:
			command = command + " -u %d" % (uid)
		if gid >= 0:
			command = command + " -g %d" % (gid)
		if homedir[0:4] != "/mnt":
			homedir = "/mnt/" + homedir
		command = command + " -s \"%s\" -d \"%s\"" % (shell, homedir)
		self.__issue_pwdchange(username, command, password)
		user = ___getpwnam(username)
		return (user.pw_uid, user.pw_gid)
	def user_changepassword(self, username, password):
		"""Changes user password"""
		command = "/usr/sbin/pw usermod \"%s\" -h 0" % (username)
		self.__issue_pwdchange(username, command, password)

def usage():
	print ("Usage: %s action command" % argv[0])
	print "    Action is one of:"
	print "        start: start a command"
	print "         stop: stop a command"
	print "      restart: restart a command"
	print "       reload: reload a command (try reload, if unsuccessful do restart"
	print "       change: notify change for a command (try self.reload, if unsuccessful do start)"
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
