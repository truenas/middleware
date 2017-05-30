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
        return self.middleware.call('zfs.pool.get_disks', pool['name'])
