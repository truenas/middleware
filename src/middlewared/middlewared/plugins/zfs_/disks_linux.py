import blkid

from middlewared.service import Service

from .disks_base import PoolDiskServiceBase


class ZFSPoolService(Service, PoolDiskServiceBase):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    def get_disks(self, name):
        disks = self.middleware.call_sync('zfs.pool.get_devices', name)
        block_devices = blkid.list_block_devices()
        mapping = {}
        for dev in filter(lambda d: not d.name.startswith('sr'), block_devices):
            mapping[dev.name] = dev.name
            if dev.partitions_exist:
                part_uuids = {
                    f'disk/by-partuuid/{p["part_uuid"]}': dev.name
                    for p in dev.__getstate__()['partitions_data']['partitions']
                }
                mapping.update(part_uuids)
                mapping.update({f'{dev.name}{i}': dev.name for i in range(1, len(part_uuids) + 1)})

        pool_disks = []
        for dev in disks:
            # dev can be partition name ( sdb1/sda2 etc ) or raw uuid ( disk/by-partuuid/uuid )
            if dev in mapping:
                pool_disks.append(mapping[dev])
            else:
                self.logger.debug(f'Could not find disk for {dev}')
        return pool_disks
