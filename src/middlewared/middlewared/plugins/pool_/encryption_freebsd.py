import asyncio
import base64
import os
import shutil
import tempfile

from libzfs import ZFSException

from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import CallError, item_method, job, private, Service, ValidationErrors


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

    @item_method
    @accepts(Int('id'), Dict(
        'pool_unlock_options',
        Str('passphrase', private=True, required=False),
        Bool('recoverykey', default=False),
        List('services_restart', default=[]),
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

        await self.middleware.call('core.bulk', 'service.restart', [
            [i] for i in set(options['services_restart']) | {'system_datasets', 'disk'} - {'jails', 'vms'}
        ])
        if 'jails' in options['services_restart']:
            await self.middleware.call('core.bulk', 'jail.rc_action', [['RESTART']])
        if 'vms' in options['services_restart']:
            for vm in await self._unlock_restarted_vms(pool['name']):
                await self.middleware.call('vm.stop', vm['id'])
                await self.middleware.call('vm.start', vm['id'])

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
        services = {
            'afp': 'AFP',
            'cifs': 'SMB',
            'ftp': 'FTP',
            'iscsitarget': 'iSCSI',
            'nfs': 'NFS',
            'webdav': 'WebDAV',
        }

        result = {}
        for k, v in services.items():
            service = await self.middleware.call('service.query', [['service', '=', k]], {'get': True})
            if service['enable'] or service['state'] == 'RUNNING':
                result[k] = v

        try:
            activated_pool = await self.middleware.call('jail.get_activated_pool')
        except Exception:
            activated_pool = None

        # If iocage is not activated yet, there is a chance that this pool might have it activated there
        if activated_pool is None:
            result['jails'] = 'Jails/Plugins'

        if await self._unlock_restarted_vms(pool['name']):
            result['vms'] = 'Virtual Machines'

        return result

    async def _unlock_restarted_vms(self, pool_name):
        result = []
        vms = (await self.middleware.call(
            'vm.query', [('autostart', '=', True)])
               )
        for vm in vms:
            for device in vm['devices']:
                if device['dtype'] not in ('DISK', 'RAW'):
                    continue

                path = device['attributes'].get('path')
                if not path:
                    continue

                if path.startswith(f'/dev/zvol/{pool_name}/') or path.startswith(f'/mnt/{pool_name}/'):
                    result.append(vm)
                    break

        return result

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

        await self.middleware.call_hook('pool.post_lock', pool=pool)
        await self.middleware.call('service.restart', 'system_datasets')
        return True
