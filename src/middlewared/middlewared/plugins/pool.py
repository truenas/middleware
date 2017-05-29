import libzfs
import os

from bsd import geom

from middlewared.schema import accepts, Int
from middlewared.service import filterable, item_method, private, CRUDService


class PoolService(CRUDService):

    @filterable
    def query(self, filters=None, options=None):
        filters = filters or []
        options = options or {}
        options['extend'] = 'pool.pool_extend'
        options['prefix'] = 'vol_'
        return self.middleware.call('datastore.query', 'storage.volume', filters, options)

    @private
    def pool_extend(self, pool):
        pool.pop('fstype', None)

        """
        If pool is encrypted we need to check if the pool is imported
        or if all geli providers exist.
        """
        if pool['encrypt'] > 0:
            try:
                libzfs.ZFS().get(pool['name'])
                pool['is_decrypted'] = True
            except libzfs.ZFSException:
                decrypted = True
                for ed in self.middleware.call('datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]):
                    if not os.path.exists(f'/dev/{ed["encrypted_provider"]}.eli'):
                        decrypted = False
                        break
                pool['is_decrypted'] = decrypted
        else:
            pool['is_decrypted'] = True
        return pool

    @item_method
    @accepts(Int('id'))
    def get_disks(self, oid):
        """
        Get all disks from a given pool `id`.
        """
        pool = self.query([('id', '=', oid)], {'get': True})
        if not pool['is_decrypted']:
            return []
        zfs = libzfs.ZFS()
        zpool = zfs.get(pool['name'])

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
