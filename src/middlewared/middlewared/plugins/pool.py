import libzfs
import os

from middlewared.schema import accepts, Int
from middlewared.service import filterable, item_method, private, CRUDService


class PoolService(CRUDService):

    @filterable
    async def query(self, filters=None, options=None):
        filters = filters or []
        options = options or {}
        options['extend'] = 'pool.pool_extend'
        options['prefix'] = 'vol_'
        return await self.middleware.call('datastore.query', 'storage.volume', filters, options)

    @private
    async def pool_extend(self, pool):
        pool.pop('fstype', None)

        """
        If pool is encrypted we need to check if the pool is imported
        or if all geli providers exist.
        """
        try:
            zpool = libzfs.ZFS().get(pool['name'])
        except libzfs.ZFSException:
            zpool = None

        pool['status'] = zpool.status if zpool else 'OFFLINE'

        if pool['encrypt'] > 0:
            if zpool:
                pool['is_decrypted'] = True
            else:
                decrypted = True
                for ed in await self.middleware.call('datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]):
                    if not os.path.exists(f'/dev/{ed["encrypted_provider"]}.eli'):
                        decrypted = False
                        break
                pool['is_decrypted'] = decrypted
        else:
            pool['is_decrypted'] = True
        return pool

    @item_method
    @accepts(Int('id'))
    async def get_disks(self, oid):
        """
        Get all disks from a given pool `id`.
        """
        pool = await self.query([('id', '=', oid)], {'get': True})
        if not pool['is_decrypted']:
            yield
        async for i in await self.middleware.call('zfs.pool.get_disks', pool['name']):
            yield i
