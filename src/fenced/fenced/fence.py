# Copyright (c) 2020 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import enum
import hashlib
import logging
import os
import sys
import sysctl
import time

from fenced.disks import Disk, Disks
from fenced.exceptions import PanicExit, ExcludeDisksError

logger = logging.getLogger(__name__)
LICENSE_FILE = '/data/license'


class ExitCode(enum.IntEnum):
    REGISTER_ERROR = 1
    REMOTE_RUNNING = 2
    RESERVE_ERROR = 3
    EXCLUDE_DISKS_ERROR = 4
    UNKNOWN = 5
    ALREADY_RUNNING = 6


class Fence(object):

    def __init__(self, interval, exclude_disks):
        self._interval = interval
        self._exclude_disks = exclude_disks.split(',') if exclude_disks else exclude_disks
        self._disks = Disks(self)
        self._reload = False
        self.hostid = None

    def get_hostid(self):
        hostid = sysctl.filter('kern.hostid')[0].value | 1 << 31
        hostid &= 0xffffffff
        # Certain Supermicro systems does not supply hostid. Workaround by using a
        # blacklist and derive the value from the license.
        if hostid == 0xfe4ac89c and os.path.exists(LICENSE_FILE):
            with open(LICENSE_FILE, 'rb') as f:
                license = hashlib.md5(f.read()).hexdigest()[:8]
                if license[0] == '0':
                    license = f'8{license[-7:]}'
                hostid = int(license, 16)
        return hostid

    def load_disks(self):

        logger.debug('Loading disks')
        self._disks.clear()
        unsupported = []
        remote_keys = set()

        disks = sysctl.filter('kern.disks')[0].value.split()
        disks = [i for i in disks if i.startswith(('da', 'nvd'))]

        # Running fenced exluding all disks is not allowed
        if not len(set(disks) - set(self._exclude_disks)):
            raise ExcludeDisksError('Excluding all disks is not allowed')

        # TODO: blacklist disks used by dumpdev
        for i in disks:

            # You can pass an "--exclude-disks" argument to fenced
            # to exclude disks from getting SCSI reservations.
            # fenced is called in 12+ with the exclusion flag
            # because the newer generation M-series are going to
            # have NVMe boot drives
            if i in self._exclude_disks:
                continue

            # try 2 times to read the keys since there are SSDs
            # that have a firmware bug that will actually barf
            # on this request. However, nothing is wrong with
            # the disk. If you simply send the same request
            # again after this error, it will return the data
            # requested with no errors.
            # (i'm looking at you STEC ZeusRAM)
            tries = 2
            for j in range(tries):
                try:
                    disk = Disk(self, i)
                    remote_keys.update(disk.get_keys()[1])
                except (OSError, RuntimeError):
                    logger.debug(
                        'Retrying to read keys for disk %s', i
                    )
                    if j < tries - 1:
                        continue
                    else:
                        unsupported.append(i)

            self._disks.add(disk)

        if unsupported:
            logger.debug('Disks without support for SCSI-3 PR: %s.', ' '.join(unsupported))

        return remote_keys

    def sighup_handler(self, signum, intr_stack_frame):
        self._reload = True

    def init(self, force):
        self.hostid = self.get_hostid()
        logger.info('Host ID: 0x%x.', self.hostid)

        remote_keys = self.load_disks()
        if not self._disks:
            logger.error('No disks available, exiting.')
            sys.exit(ExitCode.REGISTER_ERROR.value)

        if not force:
            wait_interval = 2 * self._interval + 1
            logger.info('Waiting %d seconds to verify remote keys.', wait_interval)
            time.sleep(wait_interval)
            new_remote_keys = self._disks.get_keys()[1]
            if not new_remote_keys.issubset(remote_keys):
                logger.error('Remote keys have changed, exiting.')
                sys.exit(ExitCode.REMOTE_RUNNING.value)
            else:
                logger.info('Remote keys unchanged.')

        newkey = int(time.time()) & 0xffffffff
        failed_disks = self._disks.reset_keys(newkey)
        if failed_disks:
            rate = int((len(failed_disks) / len(self._disks)) * 100)
            if rate > 10:
                logger.error('%d%% of the disks failed to reset SCSI reservations, exiting.', rate)
                sys.exit(ExitCode.RESERVE_ERROR.value)
            for disk in failed_disks:
                self._disks.remove(disk)

        logger.info('SCSI reservation set on %d disks.', len(self._disks))

        return newkey

    def loop(self, key):

        while True:

            if self._reload:
                logger.warning('SIGHUP received, reloading.')
                key = self.init(True)
                self._reload = False

            if key > 0xffffffff:
                key = 2
            else:
                key += 1

            logger.debug('Setting new key: 0x%x', key)
            failed_disks = self._disks.register_keys(key)
            if failed_disks:
                for disk in list(failed_disks):
                    try:
                        reservation = disk.get_reservation()
                        if reservation:
                            reshostid = reservation['reservation'] >> 32
                            if self.hostid != reshostid:
                                raise PanicExit(f'Reservation for at least one disk ({disk.name}) was preempted.')

                        logger.info('Trying to reset reservation for %s', disk.name)
                        disk.reset_keys(key)
                        failed_disks.remove(disk)
                    except PanicExit:
                        raise
                    except Exception:
                        pass
                if failed_disks:
                    logger.info(
                        'Disks failed to set reservation and being removed: %s',
                        ', '.join(d.name for d in failed_disks),
                    )
                for d in failed_disks:
                    self._disks.remove(d)

            time.sleep(self._interval)
