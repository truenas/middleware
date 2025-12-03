import contextlib
import errno
import os
import subprocess

from middlewared.api import api_method
from middlewared.api.current import PoolImportFindArgs, PoolImportFindResult, PoolImportPoolArgs, PoolImportPoolResult
from middlewared.plugins.container.utils import container_dataset, container_dataset_mountpoint
from middlewared.plugins.pool_.utils import UpdateImplArgs
from middlewared.plugins.zfs.mount_unmount_impl import UnmountArgs
from middlewared.service import CallError, InstanceNotFound, job, private, Service
from middlewared.utils.zfs import query_imported_fast_impl
from .utils import ZPOOL_CACHE_FILE


class PoolService(Service):

    class Config:
        cli_namespace = 'storage.pool'
        event_send = False

    @private
    async def reset_mountpoint_recursively(self, pool_name):
        """When a zpool is imported, we query only the first level
        of datasets for the zpool and check to see if the mountpoint
        is what we expect it to be. When the mountpoint is not what
        we expect, we will recursively inherit (reset) the mountpoint
        property. This usually happens when a zpool is foreign to
        TrueNAS or someone has unintentionally changed this property."""
        to_inherit = list()
        container_mnt = container_dataset_mountpoint(pool_name)
        container_ds = container_dataset(pool_name)
        for i in await self.middleware.call(
            'zfs.resource.query_impl',
            {'paths': [pool_name], 'properties': ['mountpoint'], 'max_depth': 1}
        ):
            if i['type'] != 'FILESYSTEM':
                continue
            mntpnt = i['properties']['mountpoint']['value']
            if i["name"] == pool_name:
                if mntpnt != f'/mnt/{pool_name}':
                    # yikes, someone messed with mountpoint of root dataset
                    # or this is a zpool from a non-truenas system. we have
                    # to iterate over everything and reset mountpoint before
                    # much of anything will work on our side. Furthermore,
                    # there is no reason to continue the iteration since
                    # we'll need iterate all children no matter what.
                    await self.middleware.call(
                        'pool.dataset.update_impl',
                        UpdateImplArgs(name=i['name'], zprops={'mountpoint': f'/mnt/{pool_name}'})
                    )
                    to_inherit.append(pool_name)
                    break
                else:
                    continue
            elif i['name'] == f'{pool_name}/ix-applications':
                # We exclude `ix-applications` dataset since resetting it will
                # cause PVC's to not mount because "mountpoint=legacy" is expected.
                continue

            if i['name'] == container_ds and container_mnt != mntpnt.removeprefix('/mnt'):
                # TODO: fix the "removeprefix('/mnt')" logic. /mnt is altroot
                # set at the zpool but the container_dataset_mountpoint function
                # returns the mountpoint without it. Makes using it confusing
                # and non-obvious.
                # This dataset gets a custom mountpoint so user cannot
                # unintentionally share it via SMB, NFS, etc.
                await self.middleware.call(
                    'pool.dataset.update_impl',
                    UpdateImplArgs(name=i['name'], zprops={'mountpoint': container_mnt})
                )
            elif mntpnt != f'/mnt/{i["name"]}':
                to_inherit.append(i["name"])

        if to_inherit:
            # NOTE: we use zfs.resource.query which will hide internal
            # paths. This is important so don't change it unless you
            # understand the implications fully.
            for i in await self.middleware.call(
                'zfs.resource.query',
                {'paths': to_inherit, 'properties': None, 'get_children': True}
            ):
                if i['type'] != 'FILESYSTEM':
                    continue
                try:
                    await self.middleware.call(
                        'pool.dataset.update_impl',
                        UpdateImplArgs(name=i['name'], iprops={'mountpoint'})
                    )
                except Exception:
                    self.logger.exception('Failed inheriting mountpoint property for %r', i['name'])

    @api_method(PoolImportFindArgs, PoolImportFindResult, roles=['POOL_READ'])
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

    @api_method(PoolImportPoolArgs, PoolImportPoolResult, roles=['POOL_WRITE'])
    @job(lock='import_pool')
    async def import_pool(self, job, data):
        """
        Import a pool found with `pool.import_find`.

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
        imported_pools = await self.middleware.run_in_thread(query_imported_fast_impl)
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
            pool_name = await self.middleware.run_in_thread(query_imported_fast_impl)
            pool_name = pool_name[guid]['name']
        else:
            pool_name = new_name

        # Let's umount any datasets if root dataset of the new pool is locked, and it has unencrypted datasets
        # beneath it. This is to prevent the scenario where the root dataset is locked and the child datasets
        # get mounted
        await self.handle_unencrypted_datasets_on_import(pool_name)

        # set acl properties correctly for given top-level dataset's acltype
        await self.middleware.call('pool.normalize_root_dataset_properties', pool_name, guid)

        # reset (recursively) the mountpoint property (if required)
        await self.reset_mountpoint_recursively(pool_name)

        # We want to set immutable flag on all of locked datasets
        for encrypted_ds in await self.middleware.call(
            'pool.dataset.query_encrypted_datasets', pool_name, {'key_loaded': False}
        ):
            encrypted_mountpoint = os.path.join('/mnt', encrypted_ds)
            if os.path.exists(encrypted_mountpoint):
                try:
                    await self.middleware.call('filesystem.set_zfs_attributes', {
                        'path': encrypted_mountpoint,
                        'zfs_file_attributes': {'immutable': True}
                    })
                except Exception as e:
                    self.logger.warning('Failed to set immutable flag at %r: %r', encrypted_mountpoint, e)

        # update db
        for pool in await self.middleware.call('datastore.query', 'storage.volume', [['vol_name', '=', pool_name]]):
            await self.middleware.call('datastore.delete', 'storage.volume', pool['id'])

        pool_id = await self.middleware.call('datastore.insert', 'storage.volume', {
            'vol_name': pool_name,
            'vol_guid': guid,
            'vol_all_sed': None,
        })
        if await self.middleware.call('system.is_sed_enabled'):
            self.middleware.create_task(self.middleware.call('pool.update_all_sed_attr'))

        await self.middleware.call('pool.scrub.create', {'pool': pool_id})

        # re-enable/restart any services dependent on this pool
        pool = await self.middleware.call('pool.query', [('id', '=', pool_id)], {'get': True})
        key = f'pool:{pool["name"]}:enable_on_import'
        if await self.middleware.call('keyvalue.has_key', key):
            for name, ids in (await self.middleware.call('keyvalue.get', key)).items():
                for delegate in await self.middleware.call('pool.dataset.get_attachment_delegates'):
                    if delegate.name == name:
                        attachments = await delegate.query(pool['path'], False)
                        attachments = [attachment for attachment in attachments if attachment['id'] in ids]
                        if attachments:
                            await delegate.toggle(attachments, True)
            await self.middleware.call('keyvalue.delete', key)

        await self.middleware.call_hook('pool.post_import', pool)
        await self.middleware.call('pool.dataset.sync_db_keys', pool['name'])
        self.middleware.send_event('pool.query', 'ADDED', id=pool_id, fields=pool)

        return True

    @private
    def recursive_mount(self, name):
        cmd = [
            'zfs', 'mount',
            '-R',  # recursive flag
            name,  # name of the zpool / root dataset
        ]
        try:
            self.logger.debug('Going to mount root dataset recusively: %r', name)
            cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if cp.returncode != 0:
                self.logger.error(
                    'Failed to mount datasets for pool: %r with error: %r',
                    name, cp.stdout.decode()
                )
                return False
            return True
        except Exception:
            self.logger.error(
                'Unhandled exception while mounting datasets for pool: %r',
                name, exc_info=True
            )
            return False

    @private
    def encryption_is_active(self, name):
        cmd = [
            'zfs', 'get',
            '-H',                  # use in script
            '-o', 'value',         # retrieve the value
            'encryption',          # property to retrieve
            name,                  # name of the zpool
        ]
        try:
            self.logger.debug('Checking if root dataset is encrypted: %r', name)
            cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if cp.returncode != 0:
                self.logger.error(
                    'Failed to see if root dataset is encrypted for pool: %r with error: %r',
                    name, cp.stdout.decode()
                )
                return False
            if cp.stdout.decode().strip() == 'off':
                return False
            else:
                return True
        except Exception:
            self.logger.error(
                'Unhandled exception while checking on feature@encryption for pool: %r',
                name, exc_info=True
            )
            return False

    @private
    def normalize_root_dataset_properties(self, vol_name, vol_guid):
        try:
            self.logger.debug('Calling zfs.resource.query_impl on %r with guid %r', vol_name, vol_guid)
            ds = self.middleware.call_sync(
                'zfs.resource.query_impl',
                {'paths': [vol_name], 'properties': ['acltype', 'aclinherit', 'aclmode']}
            )[0]['properties']
        except Exception:
            self.logger.warning('Unexpected failure querying root-level properties for %r', vol_name, exc_info=True)
            return True
        else:
            self.logger.debug('Done calling zfs.resource.query_impl on %r with guid %r', vol_name, vol_guid)

        opts = dict()
        if ds['acltype']['value'] == 'nfsv4':
            if ds['aclinherit']['value'] != 'passthrough':
                opts['aclinherit'] = 'passthrough'
            if ds['aclmode']['value'] != 'passthrough':
                opts['aclmode'] = 'passthrough'
        else:
            if ds['aclinherit']['value'] != 'discard':
                opts['aclinherit'] = 'discard'
            if ds['aclmode']['value'] != 'discard':
                opts['aclmode'] = 'discard'

        if opts:
            try:
                self.logger.debug('Calling pool.dateset.update_impl on %r with opts %r', vol_name, opts)
                self.middleware.call_sync('pool.dataset.update_impl', UpdateImplArgs(name=vol_name, zprops=opts))
            except Exception:
                self.logger.warning('%r: failed to normalize properties of root-level dataset', vol_name, exc_info=True)
            else:
                self.logger.debug('Done calling pool.dataset.update_impl on %r', vol_name)

    @private
    def import_on_boot_impl(self, vol_name, vol_guid, set_cachefile=False):
        cmd = [
            'zpool', 'import',
            vol_guid,  # the GUID of the zpool
            '-R', '/mnt',  # altroot
            '-m',  # import pool with missing log device(s)
            '-N',  # do not mount the datasets
            '-f',  # force import since hostid can change (upgrade from CORE to SCALE changes it, for example)
            '-o', f'cachefile={ZPOOL_CACHE_FILE}' if set_cachefile else 'cachefile=none',
        ]
        try:
            self.logger.debug('Importing %r with guid: %r', vol_name, vol_guid)
            cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if cp.returncode != 0:
                self.logger.error(
                    'Failed to import %r with guid: %r with error: %r',
                    vol_name, vol_guid, cp.stdout.decode()
                )
                return False
        except Exception:
            self.logger.error('Unhandled exception importing %r', vol_name, exc_info=True)
            return False
        else:
            self.logger.debug('Done importing %r with guid %r', vol_name, vol_guid)

        # normalize ZFS dataset properties on boot. Pool may be foreign to SCALE
        # (including those created on CORE)
        self.normalize_root_dataset_properties(vol_name, vol_guid)

        return True

    @private
    def unlock_on_boot_impl(self, vol_name):
        zpool_info = self.middleware.call_sync('pool.handle_unencrypted_datasets_on_import', vol_name)
        if not zpool_info:
            self.logger.error(
                'Unable to retrieve %r root dataset information required for unlocking any relevant encrypted datasets',
                vol_name
            )
            return

        umount_root_short_circuit = False
        if zpool_info['key_format']['parsed'] == 'passphrase':
            # passphrase encrypted zpools will _always_ fail to be unlocked at
            # boot time because we don't store the users passphrase on disk
            # anywhere.
            #
            # NOTE: To have a passphrase encrypted zpool (the root dataset is passphrase encrypted)
            # is considered an edge-case (or is someone upgrading from an old version of SCALE where
            # we mistakenly allowed this capability). There is also possibility to update existing
            # root dataset encryption from key based to passphrase based. Again, an edge-case but
            # documenting it here for posterity sake.
            self.logger.debug(
                'Passphrase encrypted zpool detected %r, passphrase required before unlock', vol_name
            )
            umount_root_short_circuit = True

        if not umount_root_short_circuit:
            # the top-level dataset could be unencrypted but there could be any number
            # of child datasets that are encrypted. This will try to recursively unlock
            # those datasets (including the parent if necessary).
            # If we fail to unlock the parent, then the method short-circuits and exits
            # early.
            opts = {'recursive': True, 'toggle_attachments': False}
            uj = self.middleware.call_sync('pool.dataset.unlock', vol_name, opts)
            uj.wait_sync()
            if uj.error:
                self.logger.error('FAILED unlocking encrypted dataset(s) for %r with error %r', vol_name, uj.error)
            elif uj.result['failed']:
                self.logger.error(
                    'FAILED unlocking the following datasets: %r for pool %r',
                    ', '.join(uj.result['failed']), vol_name
                )
            else:
                self.logger.debug('SUCCESS unlocking encrypted dataset(s) (if any) for %r', vol_name)

        if any((
            umount_root_short_circuit,
            self.middleware.call_sync(
                'pool.dataset.get_instance_quick', vol_name, {'encryption': True}
            )['locked']
        )):
            # We umount the zpool in the following scenarios:
            # 1. we came across a passphrase encrypted root dataset (i.e. /mnt/tank)
            # 2. we failed to unlock the key based encrypted root dataset
            #
            # It's important to understand how this operates at zfs level since this
            # can be painfully confusing.
            # 1. when system boots, we call zpool import
            # 2. zpool impot has no notion of encryption and will simply mount
            #   the datasets as necessary (INCLUDING ALL CHILDREN)
            # 3. if the root dataset is passphrase encrypted OR we fail to unlock
            #   the root dataset that is using key based encryption, then the child
            #   datasets ARE STILL MOUNTED DURING IMPORT PHASE (this includes
            #   encrypted children or unencrypted children)
            #
            # In the above scenario, the root dataset wouldn't be mounted but any number
            # of children would be. If the end-user is sharing one of the unencrypted children
            # via a sharing service, then what happens is that a parent DIRECTORY is created
            # in place of the root dataset and all files get written OUTSIDE of the zfs
            # mountpoint. That's an unpleasant experience because it is perceived as data loss
            # since mounting the dataset will just mount over-top of said directory.
            # (i.e. /mnt/tank/datasetA/datasetB/childds/, The "datasetA", "datasetB", "childds"
            # path components would be created as directories and I/O would continue without
            # any problems but the data is not going to that zfs dataset.
            #
            # To account for this edge-case (we now no longer allow the creation of unencrypted child
            # datasets where any upper path component is encrypted) (i.e. no more /mnt/zz/unencrypted/encrypted).
            # However, we still need to take into consideration the other users that manged to get themselves
            # into this scenario.
            if not umount_root_short_circuit:
                with contextlib.suppress(CallError):
                    self.logger.debug('Forcefully umounting %r', vol_name)
                    self.middleware.call_sync(
                        'zfs.resource.unmount',
                        UnmountArgs(filesystem=vol_name, force=True, recursive=True)
                    )
                    self.logger.debug('Successfully umounted %r', vol_name)

            pool_mount = f'/mnt/{vol_name}'
            if os.path.exists(pool_mount):
                try:
                    # setting the root path as immutable, in a perfect world, will prevent
                    # the scenario that is describe above
                    self.logger.debug('Setting immutable flag at %r', pool_mount)
                    self.middleware.call_sync('filesystem.set_zfs_attributes', {
                        'path': pool_mount,
                        'zfs_file_attributes': {'immutable': True}
                    })
                except CallError as e:
                    self.logger.error('Unable to set immutable flag at %r: %s', pool_mount, e)

    @private
    @job()
    def import_on_boot(self, job):
        if self.middleware.call_sync('failover.licensed'):
            # HA systems pools are imported using the failover
            # event logic
            return

        if self.middleware.call_sync('truenas.is_ix_hardware'):
            # Attach NVMe/RoCE - wait up to 10 seconds
            self.logger.info('Start bring up of NVMe/RoCE')
            try:
                jbof_job = self.middleware.call_sync('jbof.configure_job')
                jbof_job.wait_sync(timeout=60)
                if jbof_job.error:
                    self.logger.error(f'Error attaching JBOFs: {jbof_job.error}')
                elif jbof_job.result['failed']:
                    self.logger.error(f'Failed to attach JBOFs:{jbof_job.result["message"]}')
                else:
                    self.logger.info(jbof_job.result['message'])
            except TimeoutError:
                self.logger.error('Timed out attaching JBOFs.  Waiting again.')
                try:
                    jbof_job.wait_sync(timeout=60)
                    if jbof_job.error:
                        self.logger.error(f'Error attaching JBOFs: {jbof_job.error}')
                    elif jbof_job.result['failed']:
                        self.logger.error(f'Failed to attach JBOFs:{jbof_job.result["message"]}')
                    else:
                        self.logger.info(jbof_job.result['message'])
                except TimeoutError:
                    self.logger.error('Timed out attaching JBOFs - will continue in background.')
                else:
                    self.logger.info('Done bring up of NVMe/RoCE')
            except Exception:
                self.logger.error('Unexpected error', exc_info=True)

        set_cachefile_property = True
        dir_name = os.path.dirname(ZPOOL_CACHE_FILE)
        try:
            self.logger.debug('Creating %r (if it doesnt already exist)', dir_name)
            os.makedirs(dir_name, exist_ok=True)
        except Exception:
            self.logger.warning('FAILED unhandled exception creating %r', dir_name, exc_info=True)
            set_cachefile_property = False
        else:
            try:
                self.logger.debug('Creating %r (if it doesnt already exist)', ZPOOL_CACHE_FILE)
                with open(ZPOOL_CACHE_FILE, 'x'):
                    pass
            except FileExistsError:
                # cachefile already exists on disk which is fine
                pass
            except Exception:
                self.logger.warning('FAILED unhandled exception creating %r', ZPOOL_CACHE_FILE, exc_info=True)
                set_cachefile_property = False

        # We need to do as little zfs I/O as possible since this method
        # is being called by a systemd service at boot-up. First step of
        # doing this is to simply try to import all zpools that are in our
        # database. Handle each error accordingly instead of trying to be
        # fancy and determine which ones are "offline" since...in theory...
        # all zpools should be offline at this point.
        for i in self.middleware.call_sync('datastore.query', 'storage.volume'):
            name, guid = i['vol_name'], i['vol_guid']
            if not self.import_on_boot_impl(name, guid, set_cachefile_property):
                continue

            if not self.encryption_is_active(name):
                self.recursive_mount(name)

            self.unlock_on_boot_impl(name)

        # TODO: we need to fix this. There is 0 reason to do all this stuff
        # and block the entire boot-up process.
        self.logger.debug('Calling pool.post_import')
        self.middleware.call_hook_sync('pool.post_import', None)
        self.logger.debug('Finished calling pool.post_import')

    @private
    async def handle_unencrypted_datasets_on_import(self, pool_name):
        try:
            root_ds = await self.middleware.call('pool.dataset.get_instance_quick', pool_name, {
                'encryption': True,
            })
        except InstanceNotFound:
            # We don't really care about this case, it means that pool did not get imported for some reason
            return

        if not root_ds['encrypted']:
            return root_ds

        # If root ds is encrypted, at this point we know that root dataset has not been mounted yet and neither
        # unlocked, so if there are any children it has which were unencrypted - we force umount them
        try:
            await self.middleware.call(
                'zfs.resource.unmount',
                UnmountArgs(filesystem=pool_name, force=True, recursive=True)
            )
            self.logger.debug('Successfully umounted any unencrypted datasets under %r dataset', pool_name)
        except Exception:
            self.logger.error('Failed to umount any unencrypted datasets under %r dataset', pool_name, exc_info=True)

        return root_ds
