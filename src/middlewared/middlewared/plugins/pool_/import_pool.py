import asyncio
import contextlib
import errno
import os
import shutil

from middlewared.plugins.pool import PoolDatasetService  # FIXME: fix this after pool dataset port
from middlewared.schema import accepts, Bool, Dict, List, returns, Str
from middlewared.service import CallError, job, private, Service

from .utils import ZPOOL_CACHE_FILE, ZPOOL_KILLCACHE


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'
        event_send = False

    @accepts()
    @returns(List(
        'pools_available_for_import',
        title='Pools Available For Import',
        items=[Dict(
            'pool_info',
            Str('name', required=True),
            Str('guid', required=True),
            Str('status', required=True),
            Str('hostname', required=True),
        )]
    ))
    @job()
    async def import_find(self, job):
        """
        Returns a job id which can be used to retrieve a list of pools available for
        import with the following details as a result of the job:
        name, guid, status, hostname.
        """

        existing_guids = [i['guid'] for i in await self.middleware.call('pool.query')]

        result = []
        for pool in await self.middleware.call('zfs.pool.find_import'):
            if pool['status'] == 'UNAVAIL':
                continue
            # Exclude pools with same guid as existing pools (in database)
            # It could be the pool is in the database but was exported/detached for some reason
            # See #6808
            if pool['guid'] in existing_guids:
                continue
            entry = {}
            for i in ('name', 'guid', 'status', 'hostname'):
                entry[i] = pool[i]
            result.append(entry)
        return result

    @private
    async def disable_shares(self, ds):
        await self.middleware.call('zfs.dataset.update', ds, {
            'properties': {
                'sharenfs': {'value': "off"},
                'sharesmb': {'value': "off"},
            }
        })

    @accepts(Dict(
        'pool_import',
        Str('guid', required=True),
        Str('name'),
        Str('passphrase', private=True),
        Bool('enable_attachments'),
    ))
    @returns(Bool('successful_import'))
    @job(lock='import_pool')
    async def import_pool(self, job, data):
        """
        Import a pool found with `pool.import_find`.

        If a `name` is specified the pool will be imported using that new name.

        `passphrase` DEPRECATED. GELI not supported on SCALE.

        If `enable_attachments` is set to true, attachments that were disabled during pool export will be
        re-enabled.

        Errors:
            ENOENT - Pool not found

        .. examples(websocket)::

          Import pool of guid 5571830764813710860.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.import_pool,
                "params": [{
                    "guid": "5571830764813710860"
                }]
            }
        """
        guid = data['guid']
        new_name = data.get('name')

        # validate
        imported_pools = await self.middleware.call('zfs.pool.query_imported_fast')
        if guid in imported_pools:
            raise CallError(f'Pool with guid: "{guid}" already imported', errno.EEXIST)
        elif new_name and new_name in imported_pools.values():
            err = f'Cannot import pool using new name: "{new_name}" because a pool is already imported with that name'
            raise CallError(err, errno.EEXIST)

        # import zpool
        opts = {'altroot': '/mnt', 'cachefile': ZPOOL_CACHE_FILE}
        any_host = True
        use_cachefile = None
        await self.middleware.call('zfs.pool.import_pool', guid, opts, any_host, use_cachefile, new_name)

        # get the zpool name
        if not new_name:
            pool_name = (await self.middleware.call('zfs.pool.query_imported_fast'))[guid]['name']
        else:
            pool_name = new_name

        # set acl properties correctly for given top-level dataset's acltype
        ds = await self.middleware.call(
            'pool.dataset.query',
            [['id', '=', pool_name]],
            {'get': True, 'extra': {'retrieve_children': False}}
        )
        if ds['acltype']['value'] == 'NFSV4':
            opts = {'properties': {
                'aclinherit': {'value': 'passthrough'}
            }}
        else:
            opts = {'properties': {
                'aclinherit': {'value': 'discard'},
                'aclmode': {'value': 'discard'},
            }}

        opts['properties'].update({
            'sharenfs': {'value': 'off'}, 'sharesmb': {'value': 'off'},
        })

        await self.middleware.call('zfs.dataset.update', pool_name, opts)

        # Recursively reset dataset mountpoints for the zpool.
        recursive = True
        for child in await self.middleware.call('zfs.dataset.child_dataset_names', pool_name):
            if child == os.path.join(pool_name, 'ix-applications'):
                # We exclude `ix-applications` dataset since resetting it will
                # cause PVC's to not mount because "mountpoint=legacy" is expected.
                continue
            try:
                # Reset all mountpoints
                await self.middleware.call('zfs.dataset.inherit', child, 'mountpoint', recursive)

            except CallError as e:
                if e.errno != errno.EPROTONOSUPPORT:
                    self.logger.warning('Failed to inherit mountpoints recursively for %r dataset: %r', child, e)
                    continue

                try:
                    await self.disable_shares(child)
                    self.logger.warning('%s: disabling ZFS dataset property-based shares', child)
                except Exception:
                    self.logger.warning('%s: failed to disable share: %s.', child, str(e), exc_info=True)

            except Exception as e:
                # Let's not make this fatal
                self.logger.warning('Failed to inherit mountpoints recursively for %r dataset: %r', child, e)

        # We want to set immutable flag on all of locked datasets
        for encrypted_ds in await self.middleware.call(
                'pool.dataset.query_encrypted_datasets', pool_name, {'key_loaded': False}
        ):
            encrypted_mountpoint = os.path.join('/mnt', encrypted_ds)
            if os.path.exists(encrypted_mountpoint):
                try:
                    await self.middleware.call('filesystem.set_immutable', True, encrypted_mountpoint)
                except Exception as e:
                    self.logger.warning('Failed to set immutable flag at %r: %r', encrypted_mountpoint, e)

        # update db
        pool_id = await self.middleware.call('datastore.insert', 'storage.volume', {
            'vol_name': pool_name,
            'vol_encrypt': 0,  # TODO: remove (geli not supported)
            'vol_guid': guid,
            'vol_encryptkey': '',  # TODO: remove (geli not supported)
        })
        await self.middleware.call('pool.scrub.create', {'pool': pool_id})

        # reenable/restart any services dependent on this zpool
        pool = await self.middleware.call('pool.query', [('id', '=', pool_id)], {'get': True})
        key = f'pool:{pool["name"]}:enable_on_import'
        if await self.middleware.call('keyvalue.has_key', key):
            for name, ids in (await self.middleware.call('keyvalue.get', key)).items():
                for delegate in PoolDatasetService.attachment_delegates:
                    if delegate.name == name:
                        attachments = await delegate.query(pool['path'], False)
                        attachments = [attachment for attachment in attachments if attachment['id'] in ids]
                        if attachments:
                            await delegate.toggle(attachments, True)
            await self.middleware.call('keyvalue.delete', key)

        self.middleware.create_task(self.middleware.call('service.restart', 'collectd'))
        await self.middleware.call_hook('pool.post_import', {'passphrase': data.get('passphrase'), **pool})
        await self.middleware.call('pool.dataset.sync_db_keys', pool['name'])
        self.middleware.send_event('pool.query', 'ADDED', id=pool_id, fields=pool)

        return True

    @private
    @job()
    def import_on_boot(self, job):
        cachedir = os.path.dirname(ZPOOL_CACHE_FILE)
        if not os.path.exists(cachedir):
            os.mkdir(cachedir)

        if self.middleware.call_sync('failover.licensed'):
            return

        zpool_cache_saved = f'{ZPOOL_CACHE_FILE}.saved'
        if os.path.exists(ZPOOL_KILLCACHE):
            with contextlib.suppress(Exception):
                os.unlink(ZPOOL_CACHE_FILE)
            with contextlib.suppress(Exception):
                os.unlink(zpool_cache_saved)
        else:
            with open(ZPOOL_KILLCACHE, 'w') as f:
                os.fsync(f)

        try:
            stat = os.stat(ZPOOL_CACHE_FILE)
            if stat.st_size > 0:
                copy = False
                if not os.path.exists(zpool_cache_saved):
                    copy = True
                else:
                    statsaved = os.stat(zpool_cache_saved)
                    if stat.st_mtime > statsaved.st_mtime:
                        copy = True
                if copy:
                    shutil.copy(ZPOOL_CACHE_FILE, zpool_cache_saved)
        except FileNotFoundError:
            pass

        job.set_progress(0, 'Beginning pools import')

        pools = self.middleware.call_sync('pool.query', [
            ('encrypt', '<', 2),
            ('status', '=', 'OFFLINE')
        ])
        for i, pool in enumerate(pools):
            # Importing pools is currently 80% of the job because we may still need
            # to set ACL mode for windows
            job.set_progress(int((i + 1) / len(pools) * 80), f'Importing {pool["name"]}')
            imported = False
            if pool['guid']:
                try:
                    self.middleware.call_sync('zfs.pool.import_pool', pool['guid'], {
                        'altroot': '/mnt',
                        'cachefile': 'none',
                    }, True, zpool_cache_saved if os.path.exists(zpool_cache_saved) else None)
                except Exception:
                    # Importing a pool may fail because of out of date guid database entry
                    # or because bad cachefile. Try again using the pool name and wihout
                    # the cachefile
                    self.logger.error('Failed to import %s', pool['name'], exc_info=True)
                else:
                    imported = True
            if not imported:
                try:
                    self.middleware.call_sync('zfs.pool.import_pool', pool['name'], {
                        'altroot': '/mnt',
                        'cachefile': 'none',
                    })
                except Exception:
                    self.logger.error('Failed to import %s', pool['name'], exc_info=True)
                    continue

            try:
                self.middleware.call_sync(
                    'zfs.pool.update', pool['name'], {'properties': {
                        'cachefile': {'value': ZPOOL_CACHE_FILE},
                    }}
                )
            except Exception:
                self.logger.warning(
                    'Failed to set cache file for %s', pool['name'], exc_info=True,
                )

            unlock_job = self.middleware.call_sync(
                'pool.dataset.unlock', pool['name'], {'recursive': True, 'toggle_attachments': False}
            )
            unlock_job.wait_sync()
            if unlock_job.error or unlock_job.result['failed']:
                failed = ', '.join(unlock_job.result['failed']) if not unlock_job.error else ''
                self.logger.error(
                    f'Unlocking encrypted datasets failed for {pool["name"]} pool'
                    f'{f": {unlock_job.error}" if unlock_job.error else f" with following datasets {failed}"}'
                )

            # Child unencrypted datasets of root dataset would be mounted if root dataset is still locked,
            # we don't want that
            if self.middleware.call_sync('pool.dataset.get_instance', pool['name'])['locked']:
                with contextlib.suppress(CallError):
                    self.middleware.call_sync('zfs.dataset.umount', pool['name'], {'force': True})

                pool_mount = os.path.join('/mnt', pool['name'])
                if os.path.exists(pool_mount):
                    # We would like to ensure the path of root dataset has immutable flag set if it's not locked
                    try:
                        self.middleware.call_sync('filesystem.set_immutable', True, pool_mount)
                    except CallError as e:
                        self.logger.error('Unable to set immutable flag at %r: %s', pool_mount, e)

        with contextlib.suppress(OSError):
            os.unlink(ZPOOL_KILLCACHE)

        if os.path.exists(ZPOOL_CACHE_FILE):
            shutil.copy(ZPOOL_CACHE_FILE, zpool_cache_saved)

        # Now finally configure swap to manage any disks which might have been removed
        self.middleware.call_sync('disk.swaps_configure')
        self.middleware.call_hook_sync('pool.post_import', None)
        job.set_progress(100, 'Pools import completed')
