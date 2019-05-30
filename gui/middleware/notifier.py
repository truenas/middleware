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

import ctypes
import libzfs
import logging
import os
import re
from subprocess import Popen, PIPE
import sys
import syslog
import tempfile

WWW_PATH = "/usr/local/www"
FREENAS_PATH = os.path.join(WWW_PATH, "freenasUI")
NEED_UPDATE_SENTINEL = '/data/need-update'
GELI_KEYPATH = '/data/geli'
PWENC_FILE_SECRET = '/data/pwenc_secret'

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

from freenasUI.common.pipesubr import SIG_SETMASK
from freenasUI.common.system import (
    exclude_path,
)
from freenasUI.freeadmin.hook import HookMetaclass
from freenasUI.middleware import zfs
from freenasUI.middleware.client import client
from freenasUI.middleware.exceptions import MiddlewareError
from middlewared.plugins.pwenc import encrypt, decrypt

import sysctl

ACL_WINDOWS_FILE = ".windows"
ACL_MAC_FILE = ".mac"
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

    def geli_recoverykey_add(self, volume, passphrase=None):
        from freenasUI.middleware.util import download_job
        reckey = tempfile.NamedTemporaryFile(dir='/tmp/', delete=False)
        download_job(reckey.name, 'recovery.key', 'pool.recoverykey_add', volume.id, {})
        return reckey.name

    def geli_delkey(self, volume):
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

    def winacl_reset(self, path, owner=None, group=None, exclude=None, recursive=True):
        if exclude is None:
            exclude = []

        if isinstance(owner, bytes):
            owner = owner.decode('utf-8')

        if isinstance(group, bytes):
            group = group.decode('utf-8')

        if isinstance(path, bytes):
            path = path.decode('utf-8')

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

        with libzfs.ZFS() as zfs:
            zfs_dataset_name = zfs.get_dataset_by_path(path).name

        with client as c:
            stat = c.call('filesystem.stat', path)

        if stat['acl']:
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

    def change_upload_location(self, path):
        vardir = "/var/tmp/firmware"

        self._system("/bin/rm -rfx %s" % vardir)
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
        try:
            with client as c:
                c.call('update.create_upload_location')
        except Exception as e:
            raise MiddlewareError(str(e))

    def destroy_upload_location(self):
        """
        Destroy a temporary location for manual update
        over a memory device (mdconfig) using UFS

        Raises:
            MiddlewareError

        Returns:
            bool
        """

        try:
            with client as c:
                c.call('update.destroy_upload_location')
        except Exception as e:
            raise MiddlewareError(str(e))
        return True

    def get_update_location(self):
        with client as c:
            return c.call('update.get_update_location')

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
        with client as c:
            if unused:
                disks = c.call('disk.get_unused')
            else:
                disks = c.call('disk.query')

        for disk in disks:
            disksd.update({
                disk['devname']: {
                    'devname': disk['devname'],
                    'capacity': str(disk['size']),
                    'ident': disk['serial'],
                },
            })

        return disksd

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

        zfsproc = self._pipeopen("zfs list -t volume -o name %s -H" % sort)
        zvols = set([y for y in zfsproc.communicate()[0].split('\n') if y != ''])
        volnames = set([o.vol_name for o in Volume.objects.all()])

        fieldsflag = '-o name,used,available,referenced,mountpoint,freenas:vmsynced'
        if path:
            zfsproc = self._pipeopen("zfs list -p -r -t snapshot %s -H -S creation '%s'" % (fieldsflag, path))
        else:
            zfsproc = self._pipeopen("zfs list -p -t snapshot -H -S creation %s" % (fieldsflag))
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

    def zfs_get_options(self, name=None, recursive=False, props=None, zfstype=None):
        noinherit_fields = ['quota', 'refquota', 'reservation', 'refreservation']

        if props is None:
            props = 'all'
        else:
            props = ','.join(props)

        if zfstype is None:
            zfstype = 'filesystem,volume'

        zfsproc = self._pipeopen("zfs get %s -H -o name,property,value,source -t %s %s %s" % (
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

    def sysctl(self, name):
        """
        Tiny wrapper for sysctl module for compatibility
        """
        sysc = sysctl.filter(str(name))
        if sysc:
            return sysc[0].value
        raise ValueError(name)

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

    def pwenc_encrypt(self, text):
        if isinstance(text, bytes):
            text = text.decode('utf8')
        return encrypt(text)

    def pwenc_decrypt(self, encrypted=None):
        if not encrypted:
            return ""
        return decrypt(encrypted)


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
