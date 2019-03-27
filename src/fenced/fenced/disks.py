from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, wait as fut_wait
from functools import partial

import cam
import logging

CAM_RETRIES = 5
SET_DISKS_CAP = 30
logger = logging.getLogger(__name__)


class Disks(dict):

    def __init__(self, fence):
        self.fence = fence
        self._threadpool = ThreadPoolExecutor(max_workers=40)
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
        For better performance lets cap the number of disks we set the new key
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
        fs = {
            self._threadpool.submit(getattr(disk, method), *args): disk
            for disk in disks
        }
        done_notdone = fut_wait(fs.keys(), timeout=30)
        failed = set([fs[i] for i in done_notdone.not_done])
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
                host_key, remote_keys = i.result()
                if host_key is None:
                    failed += 1
                    return
                keys.add(key)
                remote_keys.union(remote_keys)
            except Exception:
                failed.add(fs[i])

        failed = self._run_batch('get_keys', done_callback=callback)
        return keys, remote_keys, failed

    def set_keys(self, newkey):
        return self._run_batch('set_key', [newkey], disks=self._get_set_disks())

    def reset_keys(self, newkey):
        return self._run_batch('reset_keys', [newkey])

    def reserve_key(self):
        return self._run_batch('reserve_key')


class Disk(object):

    def __init__(self, fence, name, pool=None):
        self.fence = fence
        self.name = name
        self.pool = pool
        self.cam = cam.CamDevice(f'/dev/{name}')
        self.curkey = None

    def __repr__(self):
        return f'<Disk: {self.name}>'

    def __str__(self):
        return self.name

    def get_keys(self):
        host_key = None
        remote_keys = set()
        for key in self.cam.read_keys()['keys']:
            # First 4 bytes are the host id
            if key >> 32 == self.fence.hostid:
                host_key = key
            else:
                remote_keys.add(key)
        return [host_key, remote_keys]

    def set_key(self, newkey):
        newkey = self.fence.hostid << 32 | (newkey & 0xffffffff)
        self.cam.scsi_prout(
            reskey=self.curkey, sa_reskey=newkey, mode=cam.SCSIPersistMode.REGISTER,
            retries=CAM_RETRIES,
        )
        self.curkey = newkey

    def reset_keys(self, newkey):
        newkey = self.fence.hostid << 32 | (newkey & 0xffffffff)
        tempkey = self.fence.hostid << 32 | 0x55aa55aa
        self.cam.scsi_prout(
            sa_reskey=tempkey,
            mode=cam.SCSIPersistMode.REG_IGNORE,
            retries=CAM_RETRIES,
        )
        self.cam.scsi_prout(
            reskey=tempkey,
            mode=cam.SCSIPersistMode.CLEAR,
            retries=CAM_RETRIES,
        )
        self.cam.scsi_prout(
            sa_reskey=newkey,
            mode=cam.SCSIPersistMode.REG_IGNORE,
            retries=CAM_RETRIES,
        )
        self.curkey = newkey

    def reserve_key(self):
        self.cam.scsi_prout(
            reskey=self.curkey,
            mode=cam.SCSIPersistMode.RESERVE,
            restype=cam.SCSIPersistType.WRITE_EXCLUSIVE,
            retries=CAM_RETRIES,
        )
