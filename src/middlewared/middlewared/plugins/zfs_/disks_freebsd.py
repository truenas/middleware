from bsd import geom

from middlewared.service import Service

from .disks_base import PoolDiskServiceBase


class ZFSPoolService(Service, PoolDiskServiceBase):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    def get_disks(self, name):
        disks = self.middleware.call_sync('zfs.pool.get_devices', name)
        pool_disks = []

        geom.scan()
        labelclass = geom.class_by_name('LABEL')
        for dev in disks:
            dev = dev.replace('.eli', '')
            find = labelclass.xml.findall(f".//provider[name='{dev}']/../consumer/provider")
            name = None
            if find:
                name = geom.provider_by_id(find[0].get('ref')).geom.name
            else:
                g = geom.geom_by_name('DEV', dev)
                if g:
                    name = g.consumer.provider.geom.name

            if name and (name.startswith('multipath/') or geom.geom_by_name('DISK', name)):
                pool_disks.append(name)
            else:
                self.logger.debug(f'Could not find disk for {dev}')
        return pool_disks
