from bsd import geom

from middlewared.schema import Str, accepts
from middlewared.service import CallError, Service

import errno
import libzfs


class ZFSPoolService(Service):

    class Config:
        namespace = 'zfs.pool'
        private = True

    @accepts(Str('pool'))
    def get_disks(self, name):
        zfs = libzfs.ZFS()
        try:
            zpool = zfs.get(name)
        except libzfs.ZFSException as e:
            raise CallError(str(e), errno.ENOENT)

        self.middleware.threaded(geom.scan)
        labelclass = geom.class_by_name('LABEL')
        for absdev in zpool.disks:
            dev = absdev.replace('/dev/', '').replace('.eli', '')
            find = labelclass.xml.findall(f".//provider[name='{dev}']/../consumer/provider")
            name = None
            if find:
                name = geom.provider_by_id(find[0].get('ref')).geom.name
            else:
                g = geom.geom_by_name('DEV', dev)
                if g:
                    name = g.consumer.provider.geom.name

            if name and geom.geom_by_name('DISK', name):
                yield name
            else:
                self.logger.debug(f'Could not find disk for {dev}')
