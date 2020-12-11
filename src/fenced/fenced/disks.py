# Copyright (c) 2020 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from concurrent.futures import ThreadPoolExecutor, wait as fut_wait

import cam
import nvme
import logging

CAM_RETRIES = 5
SET_DISKS_CAP = 30
logger = logging.getLogger(__name__)


class Disks(dict):

    def __init__(self, fence):
        self.fence = fence
        self._set_disks = set()

    def add(self, disk):
        assert isinstance(disk, Disk)
        self[disk.name] = disk

    def remove(self, disk):
        self.pop(disk.name)

    def _get_set_disks(self):
        """
        There is no reason set keys on every disk, especially for systems with
        hundreds of them.
        For better performance let's cap the number of disks we set the new key
        per round to `SET_DISKS_CAP`.
        """
        if len(self) <= SET_DISKS_CAP:
            return self.values()

        newset = set(self.values()) - self._set_disks
        if newset:
            if len(newset) > SET_DISKS_CAP:
                newset = set(list(newset)[:SET_DISKS_CAP])
                self._set_disks.update(newset)
            else:
                newset.update(set(list(self.values())[:SET_DISKS_CAP - len(newset)]))
                self._set_disks = newset
            return newset
        else:
            self._set_disks = set(list(self.values())[:SET_DISKS_CAP])
            return self._set_disks

    def _run_batch(self, method, args=None, disks=None, done_callback=None):
        """
        Helper method to run a batch of a Disk method
        """
        args = args or []
        disks = disks or self.values()
        executor = ThreadPoolExecutor(max_workers=SET_DISKS_CAP)
        try:
            fs = {
                executor.submit(getattr(disk, method), *args): disk
                for disk in disks
            }
            done_notdone = fut_wait(fs.keys(), timeout=30)
        finally:
            executor.shutdown(wait=False)
        failed = {fs[i] for i in done_notdone.not_done}
        if failed:
            logger.info('%s:%r timed out for %d disk(s)', method, args, len(failed))
        for i in done_notdone.done:
            if done_callback:
                done_callback(i, fs, failed)
            else:
                try:
                    i.result()
                except Exception as e:
                    disk = fs[i]
                    logger.debug('Failed to run %r %s:%r: %s', disk, method, args, e)
                    failed.add(disk)
        return failed

    def get_keys(self):
        keys = set()
        remote_keys = set()

        def callback(i, fs, failed):
            try:
                host_key, remote_key = i.result()
                remote_keys.update(remote_key)
                if host_key is None:
                    failed.add(fs[i])
                    return
                keys.add(host_key)
            except Exception:
                failed.add(fs[i])

        failed = self._run_batch('get_keys', done_callback=callback)
        return keys, remote_keys, failed

    def register_keys(self, newkey):
        return self._run_batch('register_key', [newkey], disks=self._get_set_disks())

    def reset_keys(self, newkey):
        return self._run_batch('reset_keys', [newkey])


class Disk(object):

    def __init__(self, fence, name, pool=None):
        self.fence = fence
        self.name = name
        self.pool = pool
        self.curkey = None
        self.nvme = None
        self.cam = None

        if self.name.startswith('nvd'):
            self.nvme = nvme.NvmeDevice(f'/dev/{name}')
        else:
            self.cam = cam.CamDevice(f'/dev/{name}')

    def __repr__(self):
        return f'<Disk: {self.name}>'

    def __str__(self):
        return self.name

    def get_keys(self):
        host_key = None
        remote_keys = set()

        if self.nvme:
            keys = self.nvme.read_keys()['keys']
        else:
            keys = self.cam.read_keys(retries=CAM_RETRIES)['keys']

        for key in keys:
            # First 4 bytes are the host id
            if key >> 32 == self.fence.hostid:
                host_key = key
            else:
                remote_keys.add(key)

        return (host_key, remote_keys)

    def get_reservation(self):

        if self.nvme:
            reservation = self.nvme.read_reservation()
        else:
            reservation = self.cam.read_reservation(retries=CAM_RETRIES)

        return reservation

    def register_key(self, newkey):

        newkey = self.fence.hostid << 32 | (newkey & 0xffffffff)

        if self.nvme:
            self.nvme.resvregister(
                crkey=self.curkey, nrkey=newkey, rrega=2,
            )
        else:
            self.cam.scsi_prout(
                reskey=self.curkey, sa_reskey=newkey, action=cam.SCSIPersistOutAction.REGISTER,
                retries=CAM_RETRIES,
            )

        self.curkey = newkey

    def reset_keys(self, newkey):

        reservation = self.get_reservation()
        newkey = self.fence.hostid << 32 | (newkey & 0xffffffff)

        if reservation and reservation['reservation'] >> 32 != self.fence.hostid:
            if self.nvme:
                self.nvme.resvregister(
                    nrkey=newkey,
                    rrega=0,
                )
                self.nvme.resvacquire(
                    crkey=newkey,
                    prkey=reservation['reservation'],
                    rtype=1,
                    racqa=1,
                )
            else:
                self.cam.scsi_prout(
                    sa_reskey=newkey,
                    action=cam.SCSIPersistOutAction.REG_IGNORE,
                    retries=CAM_RETRIES,
                )
                self.cam.scsi_prout(
                    reskey=newkey,
                    sa_reskey=reservation['reservation'],
                    action=cam.SCSIPersistOutAction.PREEMPT,
                    restype=cam.SCSIPersistType.WRITE_EXCLUSIVE,
                    retries=CAM_RETRIES,
                )
        else:
            if self.nvme:
                self.nvme.resvregister(
                    nrkey=newkey,
                    crkey=0 if not reservation else reservation['reservation'],
                    rrega=0 if not reservation else 2,
                    iekey=False if not reservation else True,
                )
                self.nvme.resvacquire(
                    crkey=newkey,
                    rtype=1,
                    racqa=0,
                )
            else:
                self.cam.scsi_prout(
                    sa_reskey=newkey,
                    action=cam.SCSIPersistOutAction.REG_IGNORE,
                    retries=CAM_RETRIES,
                )
                self.cam.scsi_prout(
                    reskey=newkey,
                    action=cam.SCSIPersistOutAction.RESERVE,
                    restype=cam.SCSIPersistType.WRITE_EXCLUSIVE,
                    retries=CAM_RETRIES,
                )

        self.curkey = newkey
