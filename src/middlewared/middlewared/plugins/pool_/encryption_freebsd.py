import asyncio

from middlewared.service import private, Service

ENCRYPTEDDISK_LOCK = asyncio.Lock()


class PoolService(Service):

    @private
    async def save_encrypteddisks(self, pool_id, enc_disks, disks_cache):
        async with ENCRYPTEDDISK_LOCK:
            for enc_disk in enc_disks:
                await self.middleware.call(
                    'datastore.insert',
                    'storage.encrypteddisk',
                    {
                        'volume': pool_id,
                        'disk': disks_cache[enc_disk['disk']]['identifier'],
                        'provider': enc_disk['devname'],
                    },
                    {'prefix': 'encrypted_'},
                )
