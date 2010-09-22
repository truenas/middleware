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
			if action in ("start", "stop", "restart"):
				self.__system("/usr/sbin/service " + what + " " + action)
				f = self._do_nada
			else:
				raise "Internal error: Unknown command"
		try:
			f()
		except:
			raise
	def create(self, what):
		""" Dedicated command to create "what".
		
		The helper will use method self._create_[what]() to create the object"""
		self._simplecmd("create", what)
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
		self.__system("/etc/netstart")
	def _reload_named(self):
		self.__system("/usr/sbin/service named reload")
	def _reload_general(self):
		self.__system("/usr/sbin/service hostname start")
	def _reload_ssh(self):
		self.__system("/usr/sbin/service ix-sshd start")
		self.__system("/usr/sbin/service sshd restart")
	def _reload_tftp(self):
		self.__system("/usr/sbin/service ix-inetd start")
		self.__system("/usr/sbin/service inetd restart")
	def _reload_ftp(self):
		self.__system("/usr/sbin/service ix-proftpd start")
		self.__system("/usr/sbin/service proftpd restart")
	def _reload_nfsd(self):
		self.__system("/usr/sbin/service ix-nfsd start")
		self.__system("/usr/sbin/service mountd forcerestart")
	def _restart_nfsd(self):
		self.__system("/usr/sbin/service mountd forcestop")
		self.__system("/usr/sbin/service nfsd forcestop")
		self.__system("/usr/sbin/service ix-nfsd start")
		self.__system("/usr/sbin/service nfsd start")
	def _restart_system(self):
		self.__system("/sbin/shutdown -r now")
	def _stop_system(self):
		self.__system("/sbin/shutdown -p now")
	def _reload_smbd(self):
		self.__system("/usr/sbin/service ix-samba start")
		self.__system("/usr/sbin/service samba restart")
        def _create_disk(self):
                # TODO: This accesses the database directly which should
                # be avoided
		dbname = ""
		try:
                	from freenasUI.settings import DATABASE_NAME as dbname
		except:
			dbname = '/data/freenas-v1.db'
                import sqlite3
                
                conn = sqlite3.connect(dbname)
                c = conn.cursor()
                # Create ZFS pools
                c.execute("SELECT id, name FROM freenas_volume WHERE v.type = 'zfs'")
                zfs_list = c.fetchall()
		if len(zfs_list) > 0:
			# We have to be able to write /boot/zfs and / to create mount points.
			self.__system("/sbin/mount -uw /")
			for row in zfs_list:
				z_id, z_name = row
				z_vdev = ""
				t_id = (z_id,)
				c.execute("SELECT diskgroup_id FROM freenas_volume_groups WHERE volume_id = ?", t_id)
				vgroup_list = c.fetchall()
				for vgrp in vgroup_list:
					c.execute("SELECT type FROM freenas_diskgroup WHERE id = ?", vgrp)
					vgrp_type = c.fetchone()[0]
					# TODO: Currently the volume manager does not give the expected blank
					# in database.
					if vgrp_type != "single":
						z_vdev += " " + vgrp_type
					c.execute("SELECT freenas_disk.disks, freenas_disk.name FROM freenas_disk LEFT OUTER JOIN freenas_diskgroup_members ON freenas_disk.id = freenas_diskgroup_members.disk_id WHERE freenas_diskgroup_members.diskgroup_id = ?", vgrp)
					z_vdsk_list = c.fetchall()
					for disk in z_vdsk_list:
						self.__system("[ -e /dev/gpt/%s ] || ( gpart create -s gpt /dev/%s && gpart add -t freebsd-zfs -l %s %s )" % (disk[1], disk[0], disk[1], disk[0]))
						z_vdev += " /dev/gpt/" + disk[1]
				self.__system("zpool create -m /mnt/%s %s %s" % (z_name, z_name, z_vdev))
			self.__system("/sbin/mount -ur /")
                # Create UFS file system and newfs
                c.execute("SELECT id, name FROM freenas_volume WHERE v.type = 'zfs'")
	        ufs_list = c.fetchall()
		if len(ufs_list) > 0:
			for row in ufs_list:
				u_id, u_name = row
				t_id = (u_id,)
				c.execute("SELECT diskgroup_id FROM freenas_volume_groups WHERE volume_id = ?", t_id)
				# TODO: For now we don't support RAID levels.
				ufs_volume_id = c.fetchone()
				c.execute("SELECT freenas_disk.disks, freenas_disk.name FROM freenas_disk LEFT OUTER JOIN freenas_diskgroup_members ON freenas_disk.id = freenas_diskgroup_members.disk_id WHERE freenas_diskgroup_members.diskgroup_id = ?", ufs_volume_id)
				disk = c.fetchone()
				# TODO: Not using GPT label at this moment.
				self.__system("[ -e /dev/%sp1 ] || ( gpart create -s gpt /dev/%s && gpart add -t freebsd-ufs %s )" % (disk[0], disk[0], disk[0]))
				ufs_device = "/dev/ufs/" + disk[1]
				# TODO: Need to investigate why /dev/gpt/foo can't have label /dev/ufs/bar generated automatically
				self.__system("newfs -U -L %s /dev/%sp1" % (u_name, disk[0]))
		self._reload_disk()
        def _reload_disk(self):
		self.__system("/usr/sbin/service ix-fstab start")
		self.__system("/usr/sbin/service mountlate start")
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
