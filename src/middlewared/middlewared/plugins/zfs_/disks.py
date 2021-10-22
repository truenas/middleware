from middlewared.service import Service


class ZFSPoolService(Service):

    class Config:
        namespace = 'zfs.pool'
        private = True
        process_pool = True

    def get_disks(self, name):
        pool_disks = []
        label_xml = self.middleware.call_sync('geom.get_class_xml', 'LABEL')
        dev_xml = self.middleware.call_sync('geom.get_class_xml', 'DEV')
        disks = self.middleware.call_sync('geom.get_disks')
        for dev in self.middleware.call_sync('zfs.pool.get_devices', name):
            dev = dev.replace('.eli', '')
            found = label_xml.find(f'.//provider[name="{dev}"]/../consumer/provider')
            name = None
            if found:
                name = dev
            else:
                g = dev_xml.find(f'./geom[name="{dev}"]')
                if g:
                    name = g.find('name').text

            if name and (name.startswith('multipath/') or name in disks):
                pool_disks.append(name)
            else:
                self.logger.debug('Disk %r not found in zpool %r', dev, name)

        return pool_disks
