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

from collections import OrderedDict
from decimal import Decimal
import base64
from Crypto.Cipher import AES
import ctypes
from functools import cmp_to_key
import glob
import grp
import libzfs
import logging
import os
import platform
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
import syslog
import tarfile
import tempfile
import time
import crypt
import string
import random

WWW_PATH = "/usr/local/www"
FREENAS_PATH = os.path.join(WWW_PATH, "freenasUI")
NEED_UPDATE_SENTINEL = '/data/need-update'
VERSION_FILE = '/etc/version'
GELI_KEYPATH = '/data/geli'
GELI_KEY_SLOT = 0
GELI_RECOVERY_SLOT = 1
GELI_REKEY_FAILED = '/tmp/.rekey_failed'
SYSTEMPATH = '/var/db/system'
PWENC_BLOCK_SIZE = 32
PWENC_FILE_SECRET = '/data/pwenc_secret'
PWENC_PADDING = '{'
PWENC_CHECK = 'Donuts!'
BACKUP_SOCK = '/var/run/backupd.sock'

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

from django.db.models import Q
from django.utils.translation import ugettext as _

from freenasUI.common.acl import (ACL_FLAGS_OS_WINDOWS, ACL_WINDOWS_FILE,
                                  ACL_MAC_FILE)
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
    FREENAS_DATABASE,
    exclude_path,
    get_mounted_filesystems,
    umount,
    get_sw_name,
    domaincontroller_enabled
)
from freenasUI.common.warden import (Warden, WardenJail,
                                     WARDEN_TYPE_PLUGINJAIL,
                                     WARDEN_STATUS_RUNNING)
from freenasUI.freeadmin.hook import HookMetaclass
from freenasUI.middleware import zfs
from freenasUI.middleware.client import client, ClientException
from freenasUI.middleware.encryption import random_wipe
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
        libc.sigprocmask(signal.SIGQUIT, pmask, pomask)
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
            p = Popen(
                "(" + command + ") >/dev/null 2>&1",
                stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True, close_fds=True)
            p.communicate()
            retval = p.returncode
        finally:
            libc.sigprocmask(signal.SIGQUIT, pomask, None)
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

    def start(self, what, timeout=None, onetime=False):
        kwargs = {}
        if timeout:
            kwargs['timeout'] = timeout
        with client as c:
            return c.call('service.start', what, {'onetime': onetime}, **kwargs)

    def started(self, what, timeout=None):
        kwargs = {}
        if timeout:
            kwargs['timeout'] = timeout
        with client as c:
            return c.call('service.started', what, **kwargs)

    def stop(self, what, timeout=None, onetime=False):
        kwargs = {}
        if timeout:
            kwargs['timeout'] = timeout
        with client as c:
            return c.call('service.stop', what, {'onetime': onetime}, **kwargs)

    def restart(self, what, timeout=None, onetime=False):
        kwargs = {}
        if timeout:
            kwargs['timeout'] = timeout
        with client as c:
            return c.call('service.restart', what, {'onetime': onetime}, **kwargs)

    def reload(self, what, timeout=None, onetime=False):
        kwargs = {}
        if timeout:
            kwargs['timeout'] = timeout
        with client as c:
            return c.call('service.reload', what, {'onetime': onetime}, **kwargs)

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

    def _open_db(self):
        """Open and return a cursor object for database access."""
        try:
            from freenasUI.settings import DATABASES
            dbname = DATABASES['default']['NAME']
        except:
            dbname = '/data/freenas-v1.db'

        conn = sqlite3.connect(dbname)
        c = conn.cursor()
        return c, conn

    def __gpt_labeldisk(self, type, devname, swapsize=2):
        """Label the whole disk with GPT under the desired label and type"""

        # Calculate swap size.
        swapgb = swapsize
        swapsize = swapsize * 1024 * 1024 * 2
        # Round up to nearest whole integral multiple of 128 and subtract by 34
        # so next partition starts at mutiple of 128.
        swapsize = (int((swapsize + 127) / 128)) * 128
        # To be safe, wipe out the disk, both ends... before we start
        self._system("dd if=/dev/zero of=/dev/%s bs=1m count=32" % (devname, ))
        try:
            p1 = self._pipeopen("diskinfo %s" % (devname, ))
            size = int(int(re.sub(r'\s+', ' ', p1.communicate()[0]).split()[2]) / (1024))
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
                int(size / 1024) - 32,
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
            error = proc.communicate()[1]
            if proc.returncode != 0:
                raise MiddlewareError(f'Unable to GPT format the disk "{devname}": {error}')

        # We might need to sync with reality (e.g. devname -> uuid)
        with client as c:
            c.call('disk.sync', devname)

    def __gpt_unlabeldisk(self, devname):
        """Unlabel the disk"""
        with client as c:
            c.call('disk.swaps_remove_disks', [devname])
        self._system("gpart destroy -F /dev/%s" % devname)

        # Wipe out the partition table by doing an additional iterate of create/destroy
        self._system("gpart create -s gpt /dev/%s" % devname)
        self._system("gpart destroy -F /dev/%s" % devname)

        # We might need to sync with reality (e.g. uuid -> devname)
        with client as c:
            c.call('disk.sync', devname)

    def unlabel_disk(self, devname):
        # TODO: Check for existing GPT or MBR, swap, before blindly call __gpt_unlabeldisk
        self.__gpt_unlabeldisk(devname)

    def __encrypt_device(self, devname, diskname, volume, passphrase=None):
        from freenasUI.storage.models import Disk, EncryptedDisk

        _geli_keyfile = volume.get_geli_keyfile()

        self.__geli_setmetadata(devname, _geli_keyfile, passphrase)
        self.geli_attach_single(devname, _geli_keyfile, passphrase)

        # TODO: initialize the provider in background (wipe with random data)

        if diskname.startswith('multipath/'):
            diskobj = Disk.objects.get(
                disk_multipath_name=diskname.replace('multipath/', '')
            )
        else:
            with client as c:
                ident = c.call('disk.device_to_identifier', diskname)
            diskobj = Disk.objects.filter(disk_identifier=ident).order_by('disk_expiretime')
            if diskobj.exists():
                diskobj = diskobj[0]
            else:
                diskobj = Disk.objects.filter(disk_name=diskname).order_by('disk_expiretime')
                if diskobj.exists():
                    diskobj = diskobj[0]
                else:
                    raise ValueError("Could not find disk in cache table")
        encdiskobj = EncryptedDisk()
        encdiskobj.encrypted_volume = volume
        encdiskobj.encrypted_disk = diskobj
        encdiskobj.encrypted_provider = devname
        encdiskobj.save()

        return ("/dev/%s.eli" % devname)

    def __create_keyfile(self, keyfile, size=64, force=False):
        if force or not os.path.exists(keyfile):
            keypath = os.path.dirname(keyfile)
            if not os.path.exists(keypath):
                self._system("mkdir -p %s" % keypath)
            self._system("dd if=/dev/random of=%s bs=%d count=1" % (keyfile, size))
            if not os.path.exists(keyfile):
                raise MiddlewareError("Unable to create key file: %s" % keyfile)
        else:
            log.debug("key file %s already exists" % keyfile)

    def __geli_setmetadata(self, dev, keyfile, passphrase=None):
        self.__create_keyfile(keyfile)
        _passphrase = "-J %s" % passphrase if passphrase else "-P"
        command = "geli init -s 4096 -l 256 -B none %s -K %s %s" % (_passphrase, keyfile, dev)
        err = self._pipeerr(command)
        if err:
            raise MiddlewareError("Unable to set geli metadata on %s: %s" % (dev, err))

    def __geli_delkey(self, dev, slot=GELI_KEY_SLOT, force=False):
        command = "geli delkey -n %s %s %s" % (slot, '-f' if force else '', dev)
        err = self._pipeerr(command)
        if err:
            raise MiddlewareError("Unable to delete key %s on %s: %s" % (slot, dev, err))

    def geli_setkey(self, dev, key, slot=GELI_KEY_SLOT, passphrase=None, oldkey=None):
        command = ("geli setkey -n %s %s -K %s %s %s"
                   % (slot,
                      "-J %s" % passphrase if passphrase else "-P",
                      key,
                      "-k %s" % oldkey if oldkey else "",
                      dev))
        err = self._pipeerr(command)
        if err:
            raise MiddlewareError("Unable to set passphrase on %s: %s" % (dev, err))

    def geli_passphrase(self, volume, passphrase, rmrecovery=False):
        """
        Set a passphrase in a geli
        If passphrase is None then remove the passphrase

        Raises:
            MiddlewareError
        """
        geli_keyfile = volume.get_geli_keyfile()
        for ed in volume.encrypteddisk_set.all():
            dev = ed.encrypted_provider
            if rmrecovery:
                self.__geli_delkey(dev, GELI_RECOVERY_SLOT, force=True)
            self.geli_setkey(dev, geli_keyfile, GELI_KEY_SLOT, passphrase)

    def geli_rekey(self, volume, slot=GELI_KEY_SLOT):
        """
        Regenerates the geli global key and set it to devs
        Removes the passphrase if it was present

        Raises:
            MiddlewareError
        """

        geli_keyfile = volume.get_geli_keyfile()
        geli_keyfile_tmp = "%s.tmp" % geli_keyfile
        devs = [ed.encrypted_provider for ed in volume.encrypteddisk_set.all()]

        # keep track of which device has which key in case something goes wrong
        dev_to_keyfile = dict((dev, geli_keyfile) for dev in devs)

        # Generate new key as .tmp
        log.debug("Creating new key file: %s", geli_keyfile_tmp)
        self.__create_keyfile(geli_keyfile_tmp, force=True)
        error = None
        applied = []
        for dev in devs:
            try:
                self.geli_setkey(dev, geli_keyfile_tmp, slot)
                dev_to_keyfile[dev] = geli_keyfile_tmp
                applied.append(dev)
            except Exception as ee:
                error = str(ee)
                log.error(error)
                break

        # Try to be atomic in a certain way
        # If rekey failed for one of the devs, revert for the ones already applied
        if error:
            could_not_restore = False
            for dev in applied:
                try:
                    self.geli_setkey(dev, geli_keyfile, slot, oldkey=geli_keyfile_tmp)
                    dev_to_keyfile[dev] = geli_keyfile
                except Exception as ee:
                    # this is very bad for the user, at the very least there
                    # should be a notification that they will need to
                    # manually rekey as they now have drives with different keys
                    could_not_restore = True
                    log.error(str(ee))
            if could_not_restore:
                try:
                    open(GELI_REKEY_FAILED, 'w').close()
                except:
                    pass
                log.error("Unable to rekey. Devices now have the following keys:%s%s",
                          os.linesep,
                          os.linesep.join(['%s: %s' % (dev, keyfile)
                                           for dev, keyfile in dev_to_keyfile]))
                raise MiddlewareError("Unable to rekey and devices have different "
                                      "keys. See the log file.")
            else:
                raise MiddlewareError("Unable to set key: %s" % (error, ))
        else:
            if os.path.exists(GELI_REKEY_FAILED):
                try:
                    os.unlink(GELI_REKEY_FAILED)
                except:
                    pass
            log.debug("%s -> %s", geli_keyfile_tmp, geli_keyfile)
            os.rename(geli_keyfile_tmp, geli_keyfile)
            if volume.vol_encrypt != 1:
                volume.vol_encrypt = 1
                volume.save()

            # Sync new file to standby node
            if not self.is_freenas() and self.failover_licensed():
                with client as c:
                    self.sync_file_send(c, geli_keyfile)

    def geli_recoverykey_add(self, volume, passphrase=None):
        reckey_file = tempfile.mktemp(dir='/tmp/')
        self.__create_keyfile(reckey_file, force=True)

        errors = []

        for ed in volume.encrypteddisk_set.all():
            dev = ed.encrypted_provider
            try:
                self.geli_setkey(dev, reckey_file, GELI_RECOVERY_SLOT, passphrase)
            except Exception as ee:
                errors.append(str(ee))

        if errors:
            raise MiddlewareError("Unable to set recovery key for %d devices: %s" % (
                len(errors),
                ', '.join(errors),
            ))
        return reckey_file

    def geli_delkey(self, volume, slot=GELI_RECOVERY_SLOT, force=True):
        for ed in volume.encrypteddisk_set.all():
            dev = ed.encrypted_provider
            self.__geli_delkey(dev, slot, force)

    def geli_is_decrypted(self, dev):
        doc = self._geom_confxml()
        geom = doc.xpath("//class[name = 'ELI']/geom[name = '%s.eli']" % (
            dev,
        ))
        if geom:
            return True
        return False

    def geli_attach_single(self, dev, key, passphrase=None, skip_existing=False):
        if skip_existing or not os.path.exists("/dev/%s.eli" % dev):
            command = "geli attach %s -k %s %s" % ("-j %s" % passphrase if passphrase else "-p",
                                                   key,
                                                   dev)
            err = self._pipeerr(command)
            if err or not os.path.exists("/dev/%s.eli" % dev):
                raise MiddlewareError("Unable to geli attach %s: %s" % (dev, err))
        else:
            log.debug("%s already attached", dev)

    def geli_attach(self, volume, passphrase=None, key=None):
        """
        Attach geli providers of a given volume

        Returns the number of providers that failed to attach
        """
        failed = 0
        geli_keyfile = key or volume.get_geli_keyfile()
        for ed in volume.encrypteddisk_set.all():
            dev = ed.encrypted_provider
            try:
                self.geli_attach_single(dev, geli_keyfile, passphrase)
            except Exception as ee:
                log.warn(str(ee))
                failed += 1
        return failed

    def geli_testkey(self, volume, passphrase=None):
        """
        Test key for geli providers of a given volume
        """
        geli_keyfile = volume.get_geli_keyfile()

        # Parse zpool status to get encrypted providers
        # EncryptedDisk table might be out of sync for some reason,
        # this is much more reliable!
        devs = self.zpool_parse(volume.vol_name).get_devs()
        for dev in devs:
            name, ext = os.path.splitext(dev.name)
            if ext == ".eli":
                try:
                    self.geli_attach_single(name,
                                            geli_keyfile,
                                            passphrase,
                                            skip_existing=True)
                except Exception as ee:
                    if str(ee).find('Wrong key') != -1:
                        return False
        return True

    def geli_clear(self, dev):
        """
        Clears the geli metadata on a provider
        """
        command = "geli clear %s" % dev
        err = self._pipeerr(command)
        if err:
            raise MiddlewareError("Unable to geli clear %s: %s" % (dev, err))

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

    def __prepare_zfs_vdev(self, disks, swapsize, encrypt, volume):
        vdevs = []
        with client as c:
            c.call('disk.swaps_remove_disks', disks)
        for disk in disks:
            self.__gpt_labeldisk(type="freebsd-zfs",
                                 devname=disk,
                                 swapsize=swapsize)

        self.__confxml = None  # Make sure to invalidate cache
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

    def create_volume(self, volume, groups=False, path=None, init_rand=False):
        """Create a ZFS volume identified by volume id"""
        swapsize = self.get_swapsize()
        z_name = str(volume.vol_name)
        z_vdev = ""
        encrypt = (volume.vol_encrypt >= 1)
        # Grab all disk groups' id matching the volume ID
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

        for vgrp in sorted(list(groups.values()), key=cmp_to_key(stripe_first)):
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

        p1 = self._pipeopen(
            "zpool create -o cachefile=/data/zfs/zpool.cache "
            "-o failmode=continue "
            "-o autoexpand=on "
            "-O compression=lz4 "
            "-O aclmode=passthrough -O aclinherit=passthrough "
            "-f -m %s -o altroot=%s %s %s" % (mountpoint, altroot, z_name, z_vdev))
        if p1.wait() != 0:
            error = ", ".join(p1.communicate()[1].split('\n'))
            raise MiddlewareError('Unable to create the pool: %s' % error)

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

        # Finally, attach new groups to the zpool.
        self._system("zpool add -f %s %s" % (z_name, z_vdev))

        # TODO: geli detach -l
        self.reload('disk')

    def create_zfs_vol(self, name, size, props=None, sparse=False):
        """Internal procedure to create ZFS volume"""
        if sparse is True:
            options = "-s "
        else:
            options = " "
        if props:
            assert isinstance(props, dict)
            for k in list(props.keys()):
                if props[k] != 'inherit':
                    options += "-o %s=%s " % (k, props[k])
        zfsproc = self._pipeopen("/sbin/zfs create %s -V '%s' '%s'" % (options, size, name))
        zfs_err = zfsproc.communicate()[1]
        zfs_error = zfsproc.wait()
        return zfs_error, zfs_err

    def create_zfs_dataset(self, path, props=None):
        """Internal procedure to create ZFS volume"""
        options = " "
        if props:
            assert isinstance(props, dict)
            for k in list(props.keys()):
                if props[k] != 'inherit':
                    options += "-o %s='%s' " % (k, str(props[k]).replace("'", "'\"'\"'"))
        zfsproc = self._pipeopen("/sbin/zfs create %s '%s'" % (options, path))
        zfs_output, zfs_err = zfsproc.communicate()
        zfs_error = zfsproc.wait()
        return zfs_error, zfs_err

    def list_zfs_vols(self, volname, sort=None):
        """Return a dictionary that contains all ZFS volumes list"""

        if sort is None:
            sort = ''
        else:
            sort = '-s %s' % sort

        zfsproc = self._pipeopen("/sbin/zfs list -p -H -o name,volsize,used,avail,refer,compression,compressratio %s -t volume -r '%s'" % (sort, str(volname),))
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

    def list_zfs_fsvols(self, system=False):
        proc = self._pipeopen("/sbin/zfs list -H -o name -t volume,filesystem")
        out, err = proc.communicate()
        out = out.split('\n')
        retval = OrderedDict()
        if system is False:
            systemdataset, basename = self.system_dataset_settings()
        if proc.returncode == 0:
            for line in out:
                if not line:
                    continue
                if system is False and basename:
                    if line == basename or line.startswith(basename + '/'):
                        continue
                retval[line] = line
        return retval

    def repl_remote_snapshots(self, repl):
        """
        Get a list of snapshots in the remote side
        """
        if repl.repl_remote.ssh_remote_dedicateduser_enabled:
            user = repl.repl_remote.ssh_remote_dedicateduser
        else:
            user = 'root'
        proc = self._pipeopen('/usr/local/bin/ssh -i /data/ssh/replication -o ConnectTimeout=3 -o BatchMode=yes -o StrictHostKeyChecking=yes -p %s "%s"@"%s" "zfs list -Ht snapshot -o name"' % (
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
        if retval is None:
            mp = self.__get_mountpath(path)
            if self.contains_jail_root(mp):
                try:
                    self.delete_plugins(force=True)
                except:
                    log.warn('Failed to delete plugins', exc_info=True)

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

    def destroy_zfs_vol(self, name, recursive=False):
        mp = self.__get_mountpath(name)
        if self.contains_jail_root(mp):
            self.delete_plugins()
        zfsproc = self._pipeopen("zfs destroy %s'%s'" % (
            '-r ' if recursive else '',
            str(name),
        ))
        retval = zfsproc.communicate()[1]
        return retval

    def __destroy_zfs_volume(self, volume):
        """Internal procedure to destroy a ZFS volume identified by volume id"""
        vol_name = str(volume.vol_name)
        mp = self.__get_mountpath(vol_name)
        if self.contains_jail_root(mp):
            self.delete_plugins()
        # First, destroy the zpool.
        disks = volume.get_disks()
        self._system("zpool destroy -f %s" % (vol_name, ))

        # Clear out disks associated with the volume
        for disk in disks:
            self.__gpt_unlabeldisk(devname=disk)

    def zfs_replace_disk(self, volume, from_label, to_disk, force=False, passphrase=None):
        """Replace disk in zfs called `from_label` to `to_disk`"""
        from freenasUI.storage.models import Disk, EncryptedDisk
        swapsize = self.get_swapsize()

        # TODO: Test on real hardware to see if ashift would persist across replace
        from_disk = self.label_to_disk(from_label)
        encrypt = (volume.vol_encrypt >= 1)

        with client as c:
            # to_disk _might_ have swap on, offline it before gpt label
            c.call('disk.swaps_remove_disks', [from_disk, to_disk])

        # Replace in-place
        if from_disk == to_disk:
            self._system('/sbin/zpool offline %s %s' % (volume.vol_name, from_label))

        self.__gpt_labeldisk(type="freebsd-zfs", devname=to_disk, swapsize=swapsize)

        # It has to be a freebsd-zfs partition there
        to_label = self.part_type_from_device('zfs', to_disk)

        if to_label == '':
            raise MiddlewareError('freebsd-zfs partition could not be found')

        self.__confxml = None  # Clear cache
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
                from_diskobj = Disk.objects.filter(disk_name=from_disk, disk_expiretime=None)
                if from_diskobj.exists():
                    EncryptedDisk.objects.filter(encrypted_volume=volume, encrypted_disk=from_diskobj[0]).delete()
                devname = self.__encrypt_device("gptid/%s" % uuid[0].text, to_disk, volume, passphrase=passphrase)

        if force:
            try:
                self.disk_wipe(devname.replace('/dev/', ''), mode='quick')
            except:
                log.debug('Failed to wipe disk {}'.format(to_disk), exc_info=True)

        p1 = self._pipeopen('/sbin/zpool replace %s%s %s %s' % ('-f ' if force else '', volume.vol_name, from_label, devname))
        stdout, stderr = p1.communicate()
        ret = p1.returncode
        if ret == 0:
            # If we are replacing a faulted disk, kick it right after replace
            # is initiated.
            if from_label.isdigit():
                self._system('/sbin/zpool detach %s %s' % (volume.vol_name, from_label))
            # TODO: geli detach -l
        else:
            error = ", ".join(stderr.split('\n'))
            if encrypt:
                self._system('/sbin/geli detach %s' % (devname, ))
            try:
                with client as c:
                    c.call('disk.swaps_configure')
            except Exception as e:
                log.warn('Failed to configure swaps', exc_info=True)
            raise MiddlewareError('Disk replacement failed: "%s"' % error)

        try:
            with client as c:
                c.call('disk.swaps_configure')
        except ClientException:
            log.warn('Failed to reconfigure swaps', exc_info=True)

        return ret

    def zfs_offline_disk(self, volume, label):
        from freenasUI.storage.models import EncryptedDisk

        # TODO: Test on real hardware to see if ashift would persist across replace
        disk = self.label_to_disk(label)

        with client as c:
            c.call('disk.swaps_remove_disks', [disk])

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

    def zfs_online_disk(self, volume, label):
        assert volume.vol_encrypt == 0

        p1 = self._pipeopen('/sbin/zpool online %s %s' % (volume.vol_name, label))
        stderr = p1.communicate()[1]
        if p1.returncode != 0:
            error = ", ".join(stderr.split('\n'))
            raise MiddlewareError('Disk online failed: "%s"' % error)

    def zfs_detach_disk(self, volume, label):
        """Detach a disk from zpool
           (more technically speaking, a replaced disk.  The replacement actually
           creates a mirror for the device to be replaced)"""

        if isinstance(volume, str):
            vol_name = volume
        else:
            vol_name = volume.vol_name

        from_disk = self.label_to_disk(label)
        if not from_disk:
            if not re.search(r'^[0-9]+$', label):
                log.warn("Could not find disk for the ZFS label %s", label)
        else:
            with client as c:
                c.call('disk.swaps_remove_disks', [from_disk])

        ret = self._system_nolog('/sbin/zpool detach %s %s' % (vol_name, label))

        if not isinstance(volume, str):
            self.sync_encrypted(volume)

        if from_disk:
            # TODO: This operation will cause damage to disk data which should be limited
            self.__gpt_unlabeldisk(from_disk)
        return ret

    def zfs_remove_disk(self, volume, label):
        """
        Remove a disk from zpool
        Cache disks, inactive hot-spares (and log devices in zfs 28) can be removed
        """

        from_disk = self.label_to_disk(label)
        with client as c:
            c.call('disk.swaps_remove_disks', [from_disk])

        p1 = self._pipeopen('/sbin/zpool remove %s %s' % (volume.vol_name, label))
        stderr = p1.communicate()[1]
        if p1.returncode != 0:
            error = ", ".join(stderr.split('\n'))
            raise MiddlewareError('Disk could not be removed: "%s"' % error)

        self.sync_encrypted(volume)

        # TODO: This operation will cause damage to disk data which should be limited
        if from_disk:
            self.__gpt_unlabeldisk(from_disk)

    def detach_volume_swaps(self, volume):
        """Detach all swaps associated with volume"""
        disks = volume.get_disks()
        with client as c:
            c.call('disk.swaps_remove_disks', [disks])

    def __get_mountpath(self, name, mountpoint_root='/mnt'):
        """Determine the mountpoint for a ZFS dataset

        It tries to divine the location of the dataset from the
        relevant command, and if all else fails, falls back to a less
        elegant method of representing the mountpoint path.

        This is done to ensure that in the event that the database and
        reality get out of synch, the user can nuke the volume/mountpoint.

        XXX: this should be done more elegantly by calling getfsent from C.

        Required Parameters:
            name: textual name for the mountable vdev or volume, e.g. 'tank',
                  'stripe', 'tank/dataset', etc.

        Optional Parameters:
            mountpoint_root: the root directory where all of the datasets and
                             volumes shall be mounted. Defaults to '/mnt'.

        Returns:
            the absolute path for the volume on the system.
        """
        p1 = self._pipeopen("zfs list -H -o mountpoint '%s'" % (name, ))
        stdout = p1.communicate()[0]
        if not p1.returncode:
            return stdout.strip()

        return os.path.join(mountpoint_root, name)

    def volume_destroy(self, volume):
        """Destroy a ZFS pool on the system

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

        Parameters:
            volume: a storage.models.Volume object.

        Raises:
            MiddlewareError: the volume could not be detached cleanly.
            MiddlewareError: the volume's mountpoint couldn't be removed.
            ValueError: 'destroy' isn't implemented for the said filesystem.
        """

        # volume_detach compatibility.
        vol_name = volume.vol_name
        vol_mountpath = self.__get_mountpath(vol_name)
        self.__destroy_zfs_volume(volume)
        self.reload('disk')
        self._encvolume_detach(volume, destroy=True)
        self.__rmdir_mountpoint(vol_mountpath)

    # Create a user in system then samba
    def __pw_with_password(self, command, password):
        pw = self._pipeopen(command)
        msg = pw.communicate("%s\n" % password)[1]
        if pw.returncode != 0:
            raise MiddlewareError("Operation could not be performed. %s" % msg)

        if msg != "":
            log.debug("Command reports %s", msg)
        return crypt.crypt(password, crypt_makeSalt())

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
        unix_hash = self.__pw_with_password(command, password)
        self.__smbpasswd(username, password)
        return unix_hash

    def group_create(self, name):
        command = '/usr/sbin/pw group add "%s"' % (
            name,
        )
        proc = self._pipeopen(command)
        errmsg = proc.communicate()[1]
        if proc.returncode != 0:
            raise MiddlewareError(_('Failed to create group %(name)s: %(msg)s') % {'name': name, 'msg': errmsg})
        grnam = self.___getgrnam(name)
        return grnam.gr_gid

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

    def user_lock(self, username):
        self._system('/usr/local/bin/smbpasswd -d "%s"' % (username))
        self._system('/usr/sbin/pw lock "%s"' % (username))
        return self.user_gethashedpassword(username)

    def user_unlock(self, username):
        self._system('/usr/local/bin/smbpasswd -e "%s"' % (username))
        self._system('/usr/sbin/pw unlock "%s"' % (username))
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
        return smb_hash

    def user_deleteuser(self, username):
        """
        Delete a user using pw(8) utility

        Returns:
            bool
        """
        self._system('/usr/local/bin/smbpasswd -x "%s"' % (username))
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

    def path_to_smb_share(self, path):
        from freenasUI.sharing.models import CIFS_Share

        try:
            share = CIFS_Share.objects.get(cifs_path=path)
        except:
            share = None

        return share

    def smb_share_to_path(self, share):
        from freenasUI.sharing.models import CIFS_Share

        try:
            path = CIFS_Share.objects.get(cifs_name=share)
        except:
            path = None

        return path

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
        except:
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
        except:
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
            except:
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
        except:
            log.debug("sharesec_delete: %s failed", delete_cmd)
            ret = False

        return ret

    def sharesec_reset(self, share, owner=None, group=None):
        if not share:
            return False

        log.debug("sharesec_reset: resetting %s to '%s:%s'", share, owner, group)

        self.sharesec_delete(share)
        return self.sharesec_add(share, owner, group)

    def winacl_reset(self, path, owner=None, group=None, exclude=None):
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
        apply_paths = [(y, ' -r ') for y in apply_paths]
        if len(apply_paths) > 1:
            apply_paths.insert(0, (path, ''))
        for apath, flags in apply_paths:
            fargs = args + "%s -p '%s' -x" % (flags, apath)
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
        syspath = self.system_dataset_path()
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
                    except:
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
        wlist = Warden().cached_list()
        for wj in wlist:
            wj = WardenJail(**wj)
            if wj.host == pjail:
                wjail = wj
                break

        if wjail is None:
            raise MiddlewareError(
                "The plugins jail is not running, start it before proceeding"
            )

        jail = None
        for j in Jls():
            if j.hostname == wjail.host:
                jail = j
                break

        # this stuff needs better error checking.. .. ..
        if jail is None:
            raise MiddlewareError(
                "The plugins jail is not running, start it before proceeding"
            )

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
            raise MiddlewareError(
                "This file was not identified as in PBI "
                "format, it might as well be corrupt."
            )

        prefix = None
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

        # For 9.x compatiblity we need to add prefix to ldconfig_paths
        # and run ldconfig in the jail before we install
        # See #23779
        if prefix:
            pipeopen_kwargs = {'env': {
                'PATH': '/sbin:/bin:/usr/sbin:/usr/bin:/usr/games:/usr/local/sbin:/usr/local/bin:/root/bin',
                'TMPDIR': '/tmp',
            }}
            Jexec(jid=jail.jid, command='/usr/sbin/sysrc -f /etc/rc.conf.d/ldconfig ldconfig_paths="/usr/lib/compat /usr/local/lib /usr/local/lib/compat/pkg %s/lib"' % prefix, pipeopen_kwargs=pipeopen_kwargs).run()

        info = pbi_info(flags=PBI_INFO_FLAGS_VERBOSE)
        res = info.run(jail=True, jid=jail.jid)
        if res[0] == 0 and res[1]:
            plugins = re.findall(r'^Name: (?P<name>\w+)$', res[1], re.M)
            if name in plugins:
                # FIXME: do pbi_update instead
                pass

        if pbifile == "/var/tmp/firmware/pbifile.pbi":
            self._system("/bin/mv /var/tmp/firmware/pbifile.pbi %s/%s" % (plugins_path, pbi))

        p = pbi_add(
            flags=PBI_ADD_FLAGS_NOCHECKSIG | PBI_ADD_FLAGS_FORCE,
            pbi="%s/%s" % ("/.plugins", pbi)
        )
        res = p.run(jail=True, jid=jail.jid)
        if res and res[0] == 0:
            if prefix:
                Jexec(jid=jail.jid, command='/usr/sbin/service ldconfig onestart', pipeopen_kwargs=pipeopen_kwargs).run()
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
            plugin.plugin_ip = jail.ip or '-'
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

            log.debug(
                "install_pbi: plugin_path = %s, oauth_file = %s",
                plugin_path,
                oauth_file
            )

            with open(oauth_file, 'w') as f:
                os.chmod(oauth_file, 0o600)
                f.write("key = %s\n" % rpctoken.key)
                f.write("secret = %s\n" % rpctoken.secret)

            try:
                log.debug("install_pbi: trying to save plugin to database")
                plugin.save()
                newplugin.append(plugin)
                log.debug("install_pbi: plugin saved to database")
                ret = True
            except Exception as e:
                log.debug("install_pbi: FAIL! %s", e)
                ret = False

        elif res and res[0] != 0:
            # pbid seems to return 255 for any kind of error
            # lets use error str output to find out what happenned
            if re.search(r'failed checksum', res[1], re.I | re.S | re.M):
                raise MiddlewareError(
                    "The file %s seems to be "
                    "corrupt, please try download it again." % (pbiname, )
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
            raise MiddlewareError(
                "This file was not identified as in PBI format, it might as "
                "well be corrupt."
            )

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

        (c, conn) = self._open_db()
        try:
            c.execute("SELECT plugin_jail FROM plugins_plugins WHERE id = %d" % plugin.id)
            row = c.fetchone()
        finally:
            conn.close()
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
            if not mp.mounted:
                continue
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
            raise MiddlewareError(
                "There was a problem cleaning up the PBI temp dirctory"
            )

        pbiname = newpbiname
        oldpbiname = "%s.pbi" % plugin.plugin_pbiname
        newpbiname = "%s.pbi" % newpbiname

        log.debug("XXX: oldpbiname = %s", oldpbiname)
        log.debug("XXX: newpbiname = %s", newpbiname)

        self.umount_filesystems_within("%s%s" % (jail_path, newprefix))

        # Create a PBI from the installed version
        p = pbi_create(
            flags=PBI_CREATE_FLAGS_BACKUP | PBI_CREATE_FLAGS_OUTDIR,
            outdir=oldpbitemp,
            pbidir=plugin.plugin_pbiname,
        )
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
        p = pbi_makepatch(
            flags=PBI_MAKEPATCH_FLAGS_OUTDIR | PBI_MAKEPATCH_FLAGS_NOCHECKSIG,
            outdir=pbitemp,
            oldpbi=oldpbifile,
            newpbi=newpbifile,
        )
        out = p.run(True, jail.jid)
        if out[0] != 0:
            raise MiddlewareError("Unable to make a PBI patch")

        pbpfile = "%s-%s_to_%s-%s.pbp" % (
            plugin.plugin_name.lower(),
            plugin.plugin_version,
            newversion,
            plugin.plugin_arch,
        )

        log.debug("XXX: pbpfile = %s", pbpfile)

        fullpbppath = "%s/%s/%s" % (jail_path, pbitemp, pbpfile)
        log.debug("XXX: fullpbppath = %s", fullpbppath)

        if not os.access(fullpbppath, os.F_OK):
            raise MiddlewareError("Unable to create PBP file")

        # Apply the upgrade patch to upgrade the PBI to the new version
        p = pbi_patch(
            flags=PBI_PATCH_FLAGS_OUTDIR | PBI_PATCH_FLAGS_NOCHECKSIG,
            outdir=pbitemp,
            pbp="%s/%s" % (pbitemp, pbpfile),
        )
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

        log.debug(
            "update_pbi: plugin_path = %s, oauth_file = %s",
            plugin_path,
            oauth_file,
        )

        with open(oauth_file, 'w') as f:
            os.chmod(oauth_file, 0o600)
            f.write("key = %s\n" % rpctoken.key)
            f.write("secret = %s\n" % rpctoken.secret)

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

            except Exception as err:
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

    def disk_check_clean(self, disk):
        doc = self._geom_confxml()
        search = doc.xpath("//class[name = 'PART']/geom[name = '%s']" % disk)
        if len(search) > 0:
            return False
        return True

    def detect_volumes(self, extra=None):
        """
        Responsible to detect existing volumes by running zpool commands

        Used by: Automatic Volume Import
        """

        volumes = []
        doc = self._geom_confxml()

        pool_name = re.compile(r'pool: (?P<name>%s).*?id: (?P<id>\d+)' % (zfs.ZPOOL_NAME_RE, ), re.I | re.M | re.S)
        p1 = self._pipeopen("zpool import")
        res = p1.communicate()[0]

        for pool, zid in pool_name.findall(res):
            # get status part of the pool
            status = res.split('id: %s\n' % zid)[1].split('pool:')[0]
            try:
                roots = zfs.parse_status(pool, doc, 'id: %s\n%s' % (zid, status))
            except Exception as e:
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

        # zpool import may fail due to readonly mountpoint but pool
        # will be imported so we make sure of that using libzfs.
        # See #24936
        imported = imp.returncode == 0
        if not imported:
            try:
                imported = libzfs.ZFS().get(name) is not None
            except libzfs.ZFSException:
                pass

        if imported:
            # Reset all mountpoints in the zpool
            self.zfs_inherit_option(name, 'mountpoint', True)
            # Remember the pool cache
            self._system("zpool set cachefile=/data/zfs/zpool.cache %s" % (name))
            # These should probably be options that are configurable from the GUI
            self._system("zfs set aclmode=passthrough '%s'" % name)
            self._system("zfs set aclinherit=passthrough '%s'" % name)
            return True
        else:
            log.error("Importing %s [%s] failed with: %s", name, id, stderr)
        return False

    def _encvolume_detach(self, volume, destroy=False):
        """Detach GELI providers after detaching volume."""
        """See bug: #3964"""
        if volume.vol_encrypt > 0:
            for ed in volume.encrypteddisk_set.all():
                try:
                    self.geli_detach(ed.encrypted_provider)
                except Exception as ee:
                    log.warn(str(ee))
                if destroy:
                    try:
                        # bye bye data, it was nice knowing ya
                        self.geli_clear(ed.encrypted_provider)
                    except Exception as ee:
                        log.warn(str(ee))
                    try:
                        os.remove(volume.get_geli_keyfile())
                    except Exception as ee:
                        log.warn(str(ee))

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
            volume: volume model object

        Raises:
            MiddlewareError: the volume could not be detached cleanly.
            MiddlewareError: the volume's mountpoint couldn't be removed.
        """

        vol_name = volume.vol_name

        succeeded = False

        vol_mountpath = self.__get_mountpath(vol_name)
        cmd = 'zpool export %s' % (vol_name)
        cmdf = 'zpool export -f %s' % (vol_name)

        self.stop("syslogd")

        p1 = self._pipeopen(cmd)
        stdout, stderr = p1.communicate()
        if p1.returncode == 0:
            succeeded = True
        else:
            p1 = self._pipeopen(cmdf)
            stdout, stderr = p1.communicate()

        self.start("syslogd")

        if not succeeded and p1.returncode:
            raise MiddlewareError('Failed to detach %s with "%s" (exited '
                                  'with %d): %s' %
                                  (vol_name, cmd, p1.returncode, stderr))

        self._encvolume_detach(volume)
        self.__rmdir_mountpoint(vol_mountpath)

    def volume_import(self, volume_name, volume_id, key=None, passphrase=None, enc_disks=None):
        from freenasUI.storage.models import Disk, EncryptedDisk, Scrub, Volume
        from freenasUI.sharing.models import AFP_Share, CIFS_Share, NFS_Share_Path, WebDAV_Share
        from freenasUI.system.alert import alertPlugins

        if enc_disks is None:
            enc_disks = []

        passfile = None
        if key and passphrase:
            encrypt = 2
            passfile = tempfile.mktemp(dir='/tmp/')
            with open(passfile, 'w') as f:
                os.chmod(passfile, 600)
                f.write(passphrase)
        elif key:
            encrypt = 1
        else:
            encrypt = 0

        model_objs = []
        try:
            volume = Volume(vol_name=volume_name, vol_encrypt=encrypt)
            volume.save()
            model_objs.append(volume)
            if encrypt > 0:
                if not os.path.exists(GELI_KEYPATH):
                    os.mkdir(GELI_KEYPATH)
                key.seek(0)
                keydata = key.read()
                with open(volume.get_geli_keyfile(), 'wb') as f:
                    f.write(keydata)
            self.volume = volume

            volume.vol_guid = volume_id
            volume.save()
            model_objs.append(Scrub.objects.create(scrub_volume=volume))

            if not self.zfs_import(volume_name, volume_id):
                raise MiddlewareError(_(
                    'The volume "%s" failed to import, '
                    'for futher details check pool status') % volume_name)
            for disk in enc_disks:
                self.geli_setkey(
                    "/dev/%s" % disk,
                    volume.get_geli_keyfile(),
                    passphrase=passfile
                )
                if disk.startswith("gptid/"):
                    diskname = self.identifier_to_device(
                        "{uuid}%s" % disk.replace("gptid/", "")
                    )
                elif disk.startswith("gpt/"):
                    diskname = self.label_to_disk(disk)
                else:
                    diskname = disk
                ed = EncryptedDisk()
                ed.encrypted_volume = volume
                ed.encrypted_disk = Disk.objects.filter(
                    disk_name=diskname,
                    disk_expiretime=None,
                )[0]
                ed.encrypted_provider = disk
                ed.save()
                model_objs.append(ed)
        except Exception:
            for obj in reversed(model_objs):
                obj.delete()
            if passfile:
                os.unlink(passfile)
            raise

        # In case volume was exported at some point and shares
        # were not deleted we need to restart/reload shares
        path = f'/mnt/{volume_name}'
        if AFP_Share.objects.filter(Q(afp_path=path) | Q(afp_path__startswith=f'{path}/')).exists():
            self.reload('afp')

        if CIFS_Share.objects.filter(Q(cifs_path=path) | Q(cifs_path__startswith=f'{path}/')).exists():
            self.reload('cifs')

        if NFS_Share_Path.objects.filter(Q(path=path) | Q(path__startswith=f'{path}/')).exists():
            self.restart('nfs')

        if WebDAV_Share.objects.filter(Q(webdav_path=path) | Q(webdav_path__startswith=f'{path}/')).exists():
            self.reload('webdav')

        self.reload("disk")
        self.start("ix-system")
        self.start("ix-syslogd")
        self.start("ix-warden")
        # FIXME: do not restart collectd again
        self.restart("system_datasets")

        alertPlugins.run()
        return volume

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

    def zfs_snapshot_list(self, path=None, replications=None, sort=None, system=False):
        from freenasUI.storage.models import Volume
        fsinfo = dict()

        if sort is None:
            sort = ''
        else:
            sort = '-s %s' % sort

        if system is False:
            systemdataset, basename = self.system_dataset_settings()

        if replications is None:
            replications = {}

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
                except:
                    snaplist = []
                    mostrecent = True
                replication = None
                for repl in replications:
                    if not (
                        fs == repl.repl_filesystem or (
                            repl.repl_userepl and fs.startswith(repl.repl_filesystem + '/')
                        )
                    ):
                        continue
                    snaps = replications[repl]
                    # Make sure remote snapshot is checked correctly
                    # when destination is root dataset
                    if '/' not in repl.repl_zfs:
                        replace = '{}/{}'.format(repl.repl_zfs, repl.repl_filesystem.rsplit('/')[-1])
                    else:
                        replace = repl.repl_zfs
                    remotename = '%s@%s' % (fs.replace(repl.repl_filesystem, replace), name)
                    if remotename in snaps:
                        replication = 'OK'
                        # TODO: Multiple replication tasks

                snaplist.insert(0, zfs.Snapshot(
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

    def rollback_zfs_snapshot(self, snapshot, force=False):
        zfsproc = self._pipeopen("zfs rollback %s'%s'" % (
            '-r ' if force else '',
            snapshot,
        ))
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
        except:
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

    def zfs_dataset_release_snapshots(self, name, recursive=False):
        name = str(name)
        retval = None
        if recursive:
            zfscmd = "/sbin/zfs list -Ht snapshot -o name -r '%s'" % (name)
        else:
            zfscmd = "/sbin/zfs list -Ht snapshot -o name -r -d 1 '%s'" % (name)
        try:
            with mntlock(blocking=False):
                zfsproc = self._pipeopen(zfscmd)
                output = zfsproc.communicate()[0]
                if output != '':
                    snapshots_list = output.splitlines()
                for snapshot_item in [_f for _f in snapshots_list if _f]:
                    snapshot = snapshot_item.split('\t')[0]
                    self._system("/sbin/zfs release -r freenas:repl %s" % (snapshot))
        except IOError:
            retval = 'Try again later.'
        return retval

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

        except:
            pass

        return iface if iface else None

    def get_default_ipv6_interface(self):
        p1 = self._pipeopen("route -nv show -inet6 default|grep 'interface:'|awk '{ print $2 }'")
        iface = p1.communicate()
        if p1.returncode != 0:
            iface = None
        try:
            iface = iface[0].strip()

        except:
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
        except:
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

        except:
            res = False

        return res

    def interface_is_ipv6(self, addr):
        res = False

        try:
            socket.inet_pton(socket.AF_INET6, addr)
            res = True

        except:
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

    def get_parent_interface(self, iface):
        from freenasUI import choices
        from freenasUI.common.sipcalc import sipcalc_type

        if not iface:
            return None

        child_iinfo = self.get_interface_info(iface)
        if not child_iinfo:
            return None

        child_ipv4_info = child_iinfo['ipv4']
        child_ipv6_info = child_iinfo['ipv6']
        if not child_ipv4_info and not child_ipv6_info:
            return None

        interfaces = choices.NICChoices(exclude_configured=False, include_vlan_parent=True)
        for iface in interfaces:
            iface = iface[0]

            iinfo = self.get_interface_info(iface)
            if not iinfo:
                continue

            ipv4_info = iinfo['ipv4']
            ipv6_info = iinfo['ipv6']

            if not ipv4_info and not ipv6_info:
                continue

            if ipv4_info:
                for i in ipv4_info:
                    if not i or 'inet' not in i or not i['inet']:
                        continue

                    st_ipv4 = sipcalc_type(i['inet'], i['netmask'])
                    if not st_ipv4:
                        continue

                    for ci in child_ipv4_info:
                        if not ci or 'inet' not in ci or not ci['inet']:
                            continue

                        if st_ipv4.in_network(ci['inet']):
                            return (iface, st_ipv4.host_address, st_ipv4.network_mask_bits)

            if ipv6_info:
                for i in ipv6_info:
                    if not i or 'inet6 ' not in i or not i['inet6']:
                        continue

                    st_ipv6 = sipcalc_type("%s/%s" % (i['inet'], i['prefixlen']))
                    if not st_ipv6:
                        continue

                    for ci in child_ipv6_info:
                        if not ci or 'inet6' not in ci or not ci['inet6']:
                            continue

                        if st_ipv6.in_network(ci['inet6']):
                            return (iface, st_ipv6.compressed_address, st_ipv6.prefix_length)

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

    def identifier_to_device(self, ident):

        if not ident:
            return None

        doc = self._geom_confxml()

        search = re.search(r'\{(?P<type>.+?)\}(?P<value>.+)', ident)
        if not search:
            return None

        tp = search.group("type")
        # We need to escape single quotes to html entity
        value = search.group("value").replace("'", "%27")

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
            search = doc.xpath("//class[name = 'DISK']/geom/provider/config[ident = '%s']/../../name" % value)
            if len(search) > 0:
                return search[0].text
            search = doc.xpath("//class[name = 'DISK']/geom/provider/config[normalize-space(ident) = normalize-space('%s')]/../../name" % value)
            if len(search) > 0:
                return search[0].text
            with client as c:
                for devname in self.__get_disks():
                    serial = c.call('disk.serial_from_device', devname)
                    if serial == value:
                        return devname
            return None

        elif tp == 'serial_lunid':
            search = doc.xpath("//class[name = 'DISK']/geom/provider/config[concat(ident,'_',lunid) = '%s']/../../name" % value)
            if len(search) > 0:
                return search[0].text
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
        p1 = self._pipeopen("zpool get -H -o value version %s" % name, logger=None)
        res, err = p1.communicate()
        if p1.returncode != 0:
            raise ValueError(err)
        res = res.rstrip('\n')
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

    def sync_disk_extra(self, disk, add=False):
        return

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
            if not vol.is_decrypted():
                continue

            try:
                zpool = self.zpool_parse(vol.vol_name)
            except Exception:
                log.warn('Failed to parse encrypted pool', exc_info=True)
                continue

            provs = []
            for dev in zpool.get_devs():
                if not dev.name.endswith(".eli"):
                    continue
                prov = dev.name[:-4]
                qs = EncryptedDisk.objects.filter(encrypted_provider=prov)
                if not qs.exists():
                    ed = EncryptedDisk()
                    ed.encrypted_volume = vol
                    ed.encrypted_provider = prov
                    disk = Disk.objects.filter(disk_name=dev.disk, disk_expiretime=None)
                    if disk.exists():
                        disk = disk[0]
                    else:
                        log.error("Could not find Disk entry for %s", dev.disk)
                        disk = None
                    ed.encrypted_disk = None
                    ed.save()
                else:
                    ed = qs[0]
                    disk = Disk.objects.filter(disk_name=dev.disk, disk_expiretime=None)
                    if disk.exists():
                        disk = disk[0]
                        if not ed.encrypted_disk or (
                            ed.encrypted_disk and ed.encrypted_disk.pk != disk.pk
                        ):
                            ed.encrypted_disk = disk
                            ed.save()
                provs.append(prov)
            for ed in EncryptedDisk.objects.filter(encrypted_volume=vol):
                if ed.encrypted_provider not in provs:
                    ed.delete()

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

        return [x for x in disks if not device_blacklist_re.match(x) and x not in blacklist_devs]

    def retaste_disks(self):
        """
        Retaste disks for GEOM metadata

        This will not work if the device is already open

        It is useful in multipath situations, for example.
        """
        disks = self.__get_disks()
        for disk in disks:
            open("/dev/%s" % disk, 'w').close()

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
        pipe = self._pipeopen("dd if=/dev/zero of=/dev/%s bs=1m count=32" % (devname, ))
        err = pipe.communicate()[1]
        if pipe.returncode != 0:
            raise MiddlewareError(
                "Failed to wipe %s: %s" % (devname, err)
            )
        try:
            p1 = self._pipeopen("diskinfo %s" % (devname, ))
            size = int(int(re.sub(r'\s+', ' ', p1.communicate()[0]).split()[2]) / (1024))
        except:
            log.error("Unable to determine size of %s", devname)
        else:
            pipe = self._pipeopen("dd if=/dev/zero of=/dev/%s bs=1m oseek=%s" % (
                devname,
                int(size / 1024) - 32,
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
            ], stdout=subprocess.PIPE, stderr=stderr, encoding='utf8')
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
        proc = self._pipeopen("/bin/ps -a -x -w -w -o pid,command | /usr/bin/grep '^ *%s' " % pid)
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

    def system_dataset_settings(self):
        from freenasUI.storage.models import Volume
        from freenasUI.system.models import SystemDataset

        try:
            systemdataset = SystemDataset.objects.all()[0]
        except:
            systemdataset = SystemDataset.objects.create()

        if not systemdataset.get_sys_uuid():
            systemdataset.new_uuid()
            systemdataset.save()

        # If there is a pool configured make sure the volume exists
        # Otherwise reset it to blank
        if systemdataset.sys_pool and systemdataset.sys_pool != 'freenas-boot':
            volume = Volume.objects.filter(vol_name=systemdataset.sys_pool)
            if not volume.exists():
                systemdataset.sys_pool = ''
                systemdataset.save()

        if not systemdataset.sys_pool and not self.is_freenas():
            # For TrueNAS default system dataset lives in boot pool
            # See #17049
            systemdataset.sys_pool = 'freenas-boot'
            systemdataset.save()
        elif not systemdataset.sys_pool:

            volume = None
            for o in Volume.objects.all().order_by(
                'vol_encrypt'
            ):
                if o.is_decrypted():
                    volume = o
                    break
            if not volume:
                return systemdataset, None
            else:
                systemdataset.sys_pool = volume.vol_name
                systemdataset.save()

        basename = '%s/.system' % systemdataset.sys_pool
        return systemdataset, basename

    def system_dataset_create(self, mount=True):

        if (
            hasattr(self, 'failover_status') and
            self.failover_status() == 'BACKUP'
        ):
            if os.path.exists(SYSTEMPATH):
                try:
                    os.unlink(SYSTEMPATH)
                except:
                    pass
            return None

        systemdataset, basename = self.system_dataset_settings()
        if not basename:
            if os.path.exists(SYSTEMPATH):
                try:
                    os.rmdir(SYSTEMPATH)
                except Exception as e:
                    log.debug("Failed to delete %s: %s", SYSTEMPATH, e)
            return systemdataset

        if not systemdataset.is_decrypted():
            return None

        self.system_dataset_rename(basename, systemdataset)

        datasets = [basename]
        for sub in (
            'cores', 'samba4', 'syslog-%s' % systemdataset.get_sys_uuid(),
            'rrd-%s' % systemdataset.get_sys_uuid(),
            'configs-%s' % systemdataset.get_sys_uuid(),
        ):
            datasets.append('%s/%s' % (basename, sub))

        createdds = False
        for dataset in datasets:
            proc = self._pipeopen('/sbin/zfs get -H -o value mountpoint "%s"' % dataset)
            stdout, stderr = proc.communicate()
            if proc.returncode == 0:
                if stdout.strip() != 'legacy':
                    self._system('/sbin/zfs set mountpoint=legacy "%s"' % dataset)

                continue

            self.create_zfs_dataset(dataset, {"mountpoint": "legacy"})
            createdds = True

        if createdds:
            self.restart('collectd')

        if not os.path.isdir(SYSTEMPATH):
            if os.path.exists(SYSTEMPATH):
                os.unlink(SYSTEMPATH)
            os.mkdir(SYSTEMPATH)

        aclmode = self.get_dataset_aclmode(basename)
        if aclmode and aclmode.lower() == 'restricted':
            self.set_dataset_aclmode(basename, 'passthrough')

        if mount:
            self.system_dataset_mount(systemdataset.sys_pool, SYSTEMPATH)

            corepath = '%s/cores' % SYSTEMPATH
            if os.path.exists(corepath):
                self._system('/sbin/sysctl kern.corefile=\'%s/%%N.core\'' % (
                    corepath,
                ))
                os.chmod(corepath, 0o775)

            self.nfsv4link()

        return systemdataset

    def system_dataset_rename(self, basename=None, sysdataset=None):
        if basename is None:
            basename = self.system_dataset_settings()[1]
        if sysdataset is None:
            sysdataset = self.system_dataset_settings()[0]

        legacydatasets = {
            'syslog': '%s/syslog' % basename,
            'rrd': '%s/rrd' % basename,
        }
        newdatasets = {
            'syslog': '%s/syslog-%s' % (basename, sysdataset.get_sys_uuid()),
            'rrd': '%s/rrd-%s' % (basename, sysdataset.get_sys_uuid()),
        }
        proc = self._pipeopen(
            'zfs list -H -o name %s' % ' '.join(
                [
                    "%s" % name
                    for name in list(legacydatasets.values()) + list(newdatasets.values())
                ]
            )
        )
        output = proc.communicate()[0].strip('\n').split('\n')
        for ident, name in list(legacydatasets.items()):
            if name in output:
                newname = newdatasets.get(ident)
                if newname not in output:

                    if ident == 'syslog':
                        self.stop('syslogd')
                    elif ident == 'rrd':
                        self.stop('collectd')

                    proc = self._pipeopen(
                        'zfs rename -f "%s" "%s"' % (name, newname)
                    )
                    errmsg = proc.communicate()[1]
                    if proc.returncode != 0:
                        log.error(
                            "Failed renaming system dataset from %s to %s: %s",
                            name,
                            newname,
                            errmsg,
                        )

                    if ident == 'syslog':
                        self.start('syslogd')
                    elif ident == 'rrd':
                        self.start('collectd')

                else:
                    # There is already a dataset using the new name
                    pass

    def system_dataset_path(self):
        if not os.path.exists(SYSTEMPATH):
            return None

        if not os.path.ismount(SYSTEMPATH):
            return None

        return SYSTEMPATH

    def system_dataset_mount(self, pool, path=SYSTEMPATH):
        systemdataset, basename = self.system_dataset_settings()
        sub = [
            'cores', 'samba4', 'syslog-%s' % systemdataset.get_sys_uuid(),
            'rrd-%s' % systemdataset.get_sys_uuid(),
            'configs-%s' % systemdataset.get_sys_uuid(),
        ]

        # Check if .system datasets are already mounted
        if os.path.ismount(path):
            return

        self._system('/sbin/mount -t zfs "%s/.system" "%s"' % (pool, path))

        for i in sub:
            if not os.path.isdir('%s/%s' % (path, i)):
                os.mkdir('%s/%s' % (path, i))

            self._system('/sbin/mount -t zfs "%s/.system/%s" "%s/%s"' % (pool, i, path, i))

    def system_dataset_umount(self, pool):
        systemdataset, basename = self.system_dataset_settings()
        sub = [
            'cores', 'samba4', 'syslog-%s' % systemdataset.get_sys_uuid(),
            'rrd-%s' % systemdataset.get_sys_uuid(),
            'configs-%s' % systemdataset.get_sys_uuid(),
        ]

        for i in sub:
            self._system('/sbin/umount -f "%s/.system/%s"' % (pool, i))

        self._system('/sbin/umount -f "%s/.system"' % pool)

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

    def system_dataset_rrd_toggle(self):
        sysdataset, basename = self.system_dataset_settings()

        # Path where collectd stores files
        rrd_path = '/var/db/collectd/rrd'
        # Path where rrd fies are stored in system dataset
        rrd_syspath = f'/var/db/system/rrd-{sysdataset.get_sys_uuid()}'

        if sysdataset.sys_rrd_usedataset:
            # Move from tmpfs to system dataset
            if os.path.exists(rrd_path):
                if os.path.islink(rrd_path):
                    # rrd path is already a link
                    # so there is nothing we can do about it
                    return False
                proc = self._pipeopen(f'rsync -a {rrd_path}/ {rrd_syspath}/')
                proc.communicate()
                return proc.returncode == 0
        else:
            # Move from system dataset to tmpfs
            if os.path.exists(rrd_path):
                if os.path.islink(rrd_path):
                    os.unlink(rrd_path)
            else:
                os.makedirs(rrd_path)
            proc = self._pipeopen(f'rsync -a {rrd_syspath}/ {rrd_path}/')
            proc.communicate()
            return proc.returncode == 0
        return False

    def system_dataset_migrate(self, _from, _to):

        rsyncs = (
            (SYSTEMPATH, '/tmp/system.new'),
        )

        os.mkdir('/tmp/system.new')
        self.system_dataset_mount(_to, '/tmp/system.new')

        restart = []
        if os.path.exists('/var/run/syslog.pid'):
            restart.append('syslogd')
            self.stop('syslogd')

        if os.path.exists('/var/run/samba4/smbd.pid'):
            restart.append('cifs')
            self.stop('cifs')

        if os.path.exists('/var/run/collectd.pid'):
            restart.append('collectd')
            self.stop('collectd')

        for src, dest in rsyncs:
            rv = self._system_nolog('/usr/local/bin/rsync -az "%s/" "%s"' % (
                src,
                dest,
            ))

        if _from and rv == 0:
            self.system_dataset_umount(_from)
            self.system_dataset_umount(_to)
            self.system_dataset_mount(_to, SYSTEMPATH)
            proc = self._pipeopen(
                '/sbin/zfs list -H -o name %s/.system|xargs zfs destroy -r' % (
                    _from,
                )
            )
            proc.communicate()

        os.rmdir('/tmp/system.new')

        for service in restart:
            self.start(service)

        self.nfsv4link()

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
            os.chmod(PWENC_FILE_SECRET, 0o600)
            f.write(secret)

        settings.stg_pwenc_check = self.pwenc_encrypt(PWENC_CHECK)
        settings.save()

        if reset_passwords:
            from freenasUI.directoryservice.models import ActiveDirectory, LDAP
            from freenasUI.services.models import DynamicDNS, WebDAV, UPS
            from freenasUI.system.models import Email
            self.pwenc_reset_model_passwd(ActiveDirectory, 'ad_bindpw')
            self.pwenc_reset_model_passwd(LDAP, 'ldap_bindpw')
            self.pwenc_reset_model_passwd(DynamicDNS, 'ddns_password')
            self.pwenc_reset_model_passwd(WebDAV, 'webdav_password')
            self.pwenc_reset_model_passwd(UPS, 'ups_monpwd')
            self.pwenc_reset_model_passwd(Email, 'em_pass')

    def pwenc_check(self):
        from freenasUI.system.models import Settings
        try:
            settings = Settings.objects.order_by('-id')[0]
        except IndexError:
            settings = Settings.objects.create()
        try:
            return self.pwenc_decrypt(settings.stg_pwenc_check) == PWENC_CHECK
        except (IOError, ValueError):
            return False

    def pwenc_get_secret(self):
        with open(PWENC_FILE_SECRET, 'rb') as f:
            secret = f.read()
        return secret

    def pwenc_encrypt(self, text):
        if isinstance(text, bytes):
            text = text.decode('utf8')
        from Crypto.Random import get_random_bytes
        from Crypto.Util import Counter

        def pad(x):
            return x + (PWENC_BLOCK_SIZE - len(x) % PWENC_BLOCK_SIZE) * PWENC_PADDING

        nonce = get_random_bytes(8)
        cipher = AES.new(
            self.pwenc_get_secret(),
            AES.MODE_CTR,
            counter=Counter.new(64, prefix=nonce),
        )
        encoded = base64.b64encode(nonce + cipher.encrypt(pad(text)))
        return encoded.decode()

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
        return cipher.decrypt(encrypted).decode('utf8').rstrip(PWENC_PADDING)

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


def crypt_makeSalt():
    return '$6$' + ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits + '.' + '/') for _ in range(16))


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
