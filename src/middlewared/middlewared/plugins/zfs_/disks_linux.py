import os
import pyudev

from middlewared.service import Service

from .disks_base import PoolDiskServiceBase


class ZFSPoolService(Service, PoolDiskServiceBase):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    def get_disks(self, name):
        disks = self.middleware.call_sync('zfs.pool.get_devices', name)
        mapping = {}
        for dev in filter(
            lambda d: not d.sys_name.startswith('sr') and d.get('DEVTYPE') in ('disk', 'partition'),
            pyudev.Context().list_devices(subsystem='block')
        ):
            if dev['DEVTYPE'] == 'disk':
                mapping[dev.sys_name] = dev.sys_name
            elif dev.get('ID_PART_ENTRY_UUID'):
                parent = dev.find_parent('block')
                mapping[dev.sys_name] = parent.sys_name
                mapping[os.path.join('disk/by-partuuid', dev['ID_PART_ENTRY_UUID'])] = parent.sys_name

        pool_disks = []
        for dev in disks:
            # dev can be partition name ( sdb1/sda2 etc ) or raw uuid ( disk/by-partuuid/uuid )
            if dev in mapping:
                pool_disks.append(mapping[dev])
            else:
                self.logger.debug(f'Could not find disk for {dev}')
        return pool_disks
