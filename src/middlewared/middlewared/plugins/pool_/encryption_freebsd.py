import asyncio
import base64
import os
import shutil
import tempfile

from libzfs import ZFSException

from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import CallError, item_method, job, private, Service, ValidationErrors

GELI_KEYPATH = '/data/geli'
ZPOOL_CACHE_FILE = '/data/zfs/zpool.cache'

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

        await self.middleware.call_hook(
            'pool.post_change_passphrase', {
                'action': 'UPDATE' if options['passphrase'] else 'REMOVE',
                'passphrase': options['passphrase'],
                'pool': pool['name'],
            }
        )
        return True

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('admin_password', private=True, required=False),
    ))
    async def rekey(self, oid, options):
        """
        Rekey encrypted pool `id`.

        .. examples(websocket)::

          Rekey pool 1.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.rekey,
                "params": [1, {
                    "admin_password": "rootpassword"
                }]
            }
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        await self.middleware.call('pool.common_encopt_validation', pool, options)
        await self.middleware.call('disk.geli_rekey', pool)
        if pool['encrypt'] == 2:
            await self.middleware.call(
                'datastore.update', 'storage.volume', oid, {'vol_encrypt': 1}
            )

        await self.middleware.call_hook('pool.rekey_done', pool=pool)
        return True

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('admin_password', private=True, required=False),
    ))
    @job(lock=lambda x: f'pool_reckey_{x[0]}', pipes=['output'])
    async def recoverykey_add(self, job, oid, options):
        """
        Add Recovery key for encrypted pool `id`.

        This is to be used with `core.download` which will provide an URL
        to download the recovery key.
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        await self.middleware.call('pool.common_encopt_validation', pool, options)
        reckey = await self.middleware.call('disk.geli_recoverykey_add', pool)
        job.pipes.output.w.write(base64.b64decode(reckey))
        job.pipes.output.w.close()
        return True

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('admin_password', private=True, required=False),
    ))
    async def recoverykey_rm(self, oid, options):
        """
        Remove recovery key for encrypted pool `id`.

        .. examples(websocket)::

          Remove recovery key for pool 1.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.recoverykey_rm,
                "params": [1, {
                    "admin_password": "rootpassword"
                }]
            }
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        await self.middleware.call('pool.common_encopt_validation', pool, options)
        await self.middleware.call('disk.geli_recoverykey_rm', pool)
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
        return verrors

    @item_method
    @accepts(Int('id'), Dict(
        'pool_unlock_options',
        Str('passphrase', private=True, required=False),
        Bool('recoverykey', default=False),
        List('services_restart'),
        register=True,
    ))
    @job(lock='unlock_pool', pipes=['input'], check_pipes=False)
    async def unlock(self, job, oid, options):
        """
        Unlock encrypted pool `id`.

        `passphrase` is required of a recovery key is not provided.

        If `recoverykey` is true this method expects the recovery key file to be uploaded using
        the /_upload/ endpoint.

        `services_restart` is a list of services to be restarted when the pool gets unlocked.
        Said list be be retrieve using `pool.unlock_services_restart_choices`.

        .. examples(websocket)::

          Unlock pool of id 1, restarting "cifs" service.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.unlock,
                "params": [1, {
                    "passphrase": "mysecretpassphrase",
                    "services_restart": ["cifs"]
                }]
            }
        """
        pool = await self.middleware.call('pool.get_instance', oid)

        verrors = ValidationErrors()

        if pool['encrypt'] == 0:
            verrors.add('id', 'Pool is not encrypted.')
        elif pool['status'] != 'OFFLINE':
            verrors.add('id', 'Pool already unlocked.')

        if options.get('passphrase') and options['recoverykey']:
            verrors.add(
                'options.passphrase', 'Either provide a passphrase or a recovery key, not both.'
            )
        elif not options.get('passphrase') and not options['recoverykey']:
            verrors.add(
                'options.passphrase', 'Provide a passphrase or a recovery key.'
            )

        if verrors:
            raise verrors

        if options['recoverykey']:
            job.check_pipe("input")
            with tempfile.NamedTemporaryFile(mode='wb+', dir='/tmp/') as f:
                os.chmod(f.name, 0o600)
                await self.middleware.run_in_thread(shutil.copyfileobj, job.pipes.input.r, f)
                await self.middleware.run_in_thread(f.flush)
                failed = await self.middleware.call('disk.geli_attach', pool, None, f.name)
        else:
            failed = await self.middleware.call('disk.geli_attach', pool, options['passphrase'])

        # We need to try to import the pool even if some disks failed to attach
        try:
            await self.middleware.call('zfs.pool.import_pool', pool['guid'], {
                'altroot': '/mnt',
                'cachefile': ZPOOL_CACHE_FILE,
            })
        except Exception as e:
            # mounting filesystems may fail if we have readonly datasets as parent
            if not isinstance(e, ZFSException) or e.code.name != 'MOUNTFAILED':
                detach_failed = await self.middleware.call('disk.geli_detach', pool)
                if failed > 0:
                    msg = f'Pool could not be imported: {failed} devices failed to decrypt.'
                    if detach_failed > 0:
                        msg += (
                            f' {detach_failed} devices failed to detach and were left decrypted.'
                        )
                    raise CallError(msg)
                elif detach_failed > 0:
                    self.logger.warn('Pool %s failed to import', pool['name'], exc_info=True)
                    raise CallError(f'Pool could not be imported ({detach_failed} devices left decrypted): {str(e)}')
                raise e

        await self.middleware.call('pool.sync_encrypted', oid)

        await self.middleware.call(
            'pool.dataset.restart_services_after_unlock', pool['name'],
            set(options['services_restart']) | {'system_datasets', 'disk'}
        )

        await self.middleware.call_hook(
            'pool.post_unlock', pool=pool, passphrase=options.get('passphrase'),
        )

        return True

    @accepts(Int('id'))
    async def unlock_services_restart_choices(self, oid):
        """
        Get a mapping of services identifiers and labels that can be restart
        on volume unlock.
        """
        pool = await self.middleware.call('pool.get_instance', oid)
        return await self.middleware.call('pool.dataset.unlock_services_restart_choices', pool['name'])

    @private
    async def pool_lock_pre_check(self, pool, passphrase):
        verrors = ValidationErrors()

        # Make sure that this pool is not being used by system dataset service
        if pool['name'] == (await self.middleware.call('systemdataset.config'))['pool']:
            verrors.add(
                'id',
                f'Pool {pool["name"]} contains the system dataset. The system dataset pool cannot be locked.'
            )
        else:
            if not await self.middleware.call('disk.geli_testkey', pool, passphrase):
                verrors.add(
                    'passphrase',
                    'The entered passphrase was not valid. Please enter the correct passphrase to lock the pool.'
                )

        return verrors

    @item_method
    @accepts(Int('id'), Str('passphrase', private=True))
    @job(lock='lock_pool')
    async def lock(self, job, oid, passphrase):
        """
        Lock encrypted pool `id`.
        """
        pool = await self.middleware.call('pool.get_instance', oid)

        verrors = ValidationErrors()

        if pool['encrypt'] == 0:
            verrors.add('id', 'Pool is not encrypted.')
        elif pool['status'] == 'OFFLINE':
            verrors.add('id', 'Pool already locked.')

        if not verrors:
            verrors.extend(await self.middleware.call('pool.pool_lock_pre_check', pool, passphrase))

        if verrors:
            raise verrors

        await self.middleware.call_hook('pool.pre_lock', pool=pool)

        sysds = await self.middleware.call('systemdataset.config')
        if sysds['pool'] == pool['name']:
            sysds_update_job = await self.middleware.call('systemdataset.update', {
                'pool': None, 'pool_exclude': pool['name'],
            })
            await sysds_update_job.wait()
            if sysds_update_job.error:
                raise CallError(sysds_update_job.error)

        await self.middleware.call('zfs.pool.export', pool['name'])

        for ed in await self.middleware.call(
            'datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]
        ):
            await self.middleware.call('disk.geli_detach_single', ed['encrypted_provider'])

        await self.middleware.call_hook('pool.post_lock', pool=pool['name'])
        await self.middleware.call('service.restart', 'system_datasets')
        return True

    @item_method
    @accepts(Int('id'), Str('filename', default='geli.key'))
    async def download_encryption_key(self, oid, filename):
        """
        Download encryption key for a given pool `id`.
        """
        pool = await self.middleware.call('pool.query', [('id', '=', oid)], {'get': True})
        if not pool['encryptkey']:
            return None

        job_id, url = await self.middleware.call(
            'core.download',
            'filesystem.get',
            [os.path.join(GELI_KEYPATH, f'{pool["encryptkey"]}.key')],
            filename,
        )
        return url

    @staticmethod
    def __get_dev_and_disk(topology):
        rv = []
        for values in topology.values():
            values = values.copy()
            while values:
                value = values.pop()
                if value['type'] == 'DISK':
                    rv.append((value['path'].replace('/dev/', ''), value['disk']))
                values += value.get('children') or []
        return rv

    @private
    async def remove_from_storage_encrypted_disk(self, id_or_filters):
        async with ENCRYPTEDDISK_LOCK:
            await self.middleware.call('datastore.delete', 'storage.encrypteddisk', id_or_filters)

    @private
    async def sync_encrypted(self, pool=None):
        """
        This syncs the EncryptedDisk table with the current state
        of a volume
        """
        if pool is not None:
            filters = [('id', '=', pool)]
        else:
            filters = []

        pools = await self.middleware.call('pool.query', filters)
        if not pools:
            return

        # Grab all disks at once to avoid querying every iteration
        disks = {i['devname']: i['identifier'] for i in await self.middleware.call('disk.query')}

        async with ENCRYPTEDDISK_LOCK:
            for pool in pools:
                if not pool['is_decrypted'] or pool['status'] == 'OFFLINE' or pool['encrypt'] == 0:
                    continue

                provs = []
                for dev, disk in self.__get_dev_and_disk(pool['topology']):
                    if not dev.endswith(".eli"):
                        continue
                    prov = dev[:-4]
                    diskid = disks.get(disk)
                    ed = await self.middleware.call('datastore.query', 'storage.encrypteddisk', [
                        ('encrypted_provider', '=', prov)
                    ])
                    if not ed:
                        if not diskid:
                            self.logger.warn('Could not find Disk entry for %s', disk)
                        await self.middleware.call('datastore.insert', 'storage.encrypteddisk', {
                            'encrypted_volume': pool['id'],
                            'encrypted_provider': prov,
                            'encrypted_disk': diskid,
                        })
                    elif diskid and ed[0]['encrypted_disk'] != diskid:
                        await self.middleware.call(
                            'datastore.update', 'storage.encrypteddisk', ed[0]['id'],
                            {'encrypted_disk': diskid},
                        )
                    provs.append(prov)

                # Delete devices no longer in pool from database
                await self.middleware.call('datastore.delete', 'storage.encrypteddisk', [
                    ('encrypted_volume', '=', pool['id']), ('encrypted_provider', 'nin', provs)
                ])
