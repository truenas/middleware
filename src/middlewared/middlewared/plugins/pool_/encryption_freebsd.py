import asyncio

from middlewared.schema import accepts, Dict, Int, Str
from middlewared.service import item_method, private, Service, ValidationErrors

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

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('passphrase', private=True, required=True, null=True),
        Str('admin_password', private=True),
    ))
    async def passphrase(self, oid, options):
        """
        Create/Change/Remove passphrase for an encrypted pool.

        Setting passphrase to null will remove the passphrase.
        `admin_password` is required when changing or removing passphrase.

        .. examples(websocket)::

          Change passphrase for pool 1.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.passphrase,
                "params": [1, {
                    "passphrase": "mysecretpassphrase",
                    "admin_password": "rootpassword"
                }]
            }
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        verrors = await self.common_encopt_validation(pool, options)
        if (
            pool['name'] == (await self.middleware.call('systemdataset.config'))['pool'] and (
                pool['encrypt'] == 1 or (pool['encrypt'] == 2 and options['passphrase'])
            )
        ):
            # Only allow removing passphrase for pools being used by system dataset service
            verrors.add(
                'id',
                f'Pool {pool["name"]} contains the system dataset. Passphrases are not allowed on the '
                'system dataset pool.'
            )

        # For historical reasons (API v1.0 compatibility) we only require
        # admin_password when changing/removing passphrase
        if pool['encrypt'] == 2 and not options.get('admin_password'):
            verrors.add('options.admin_password', 'This attribute is required.')

        verrors.check()

        await self.middleware.call('disk.geli_passphrase', pool, options['passphrase'], True)

        if pool['encrypt'] == 1 and options['passphrase']:
            await self.middleware.call(
                'datastore.update', 'storage.volume', oid, {'vol_encrypt': 2}
            )
        elif pool['encrypt'] == 2 and not options['passphrase']:
            await self.middleware.call(
                'datastore.update', 'storage.volume', oid, {'vol_encrypt': 1}
            )
        return True

    @private
    async def common_encopt_validation(self, pool, options):
        verrors = ValidationErrors()

        if pool['encrypt'] == 0:
            verrors.add('id', 'Pool is not encrypted.')

        # admin password is optional, its choice of the client to enforce
        # it or not.
        if 'admin_password' in options and not await self.middleware.call(
            'auth.check_user', 'root', options['admin_password']
        ):
            verrors.add('options.admin_password', 'Invalid admin password.')

        verrors.check()
