import pyudev

from middlewared.service import Service


class ZFSPoolService(Service):

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

            for link in (dev.get('DEVLINKS') or '').split():
                mapping[link[len('/dev/'):]] = dev.sys_name

        pool_disks = []
        for dev in disks:
            # dev can be partition name ( sdb1/sda2 etc ) or raw uuid ( disk/by-partuuid/uuid )
            if dev in mapping:
                pool_disks.append(mapping[dev])
            else:
                self.logger.debug(f'Could not find disk for {dev}')
        return pool_disks
