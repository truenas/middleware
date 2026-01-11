import errno
import json
import os
import shutil
import subprocess
import tempfile
import truenas_os
import uuid

from contextlib import contextmanager, suppress
from pathlib import Path

import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    SystemDatasetEntry, SystemDatasetPoolChoicesArgs, SystemDatasetPoolChoicesResult, SystemDatasetUpdateArgs,
    SystemDatasetUpdateResult
)
from middlewared.plugins.system_dataset.hierarchy import get_system_dataset_spec
from middlewared.plugins.system_dataset.mount import mount_hierarchy
from middlewared.plugins.system_dataset.utils import SYSDATASET_PATH
from middlewared.plugins.pool_.utils import CreateImplArgs, UpdateImplArgs
from middlewared.plugins.zfs.utils import get_encryption_info
from middlewared.service import CallError, ConfigService, ValidationError, ValidationErrors, job, private
from middlewared.utils import MIDDLEWARE_RUN_DIR, BOOT_POOL_NAME_VALID
from middlewared.utils.directoryservices.constants import DSStatus, DSType
from middlewared.utils.filter_list import filter_list
from middlewared.utils.mount import statmount, getmntinfo, iter_mountinfo
from middlewared.utils.size import format_size
from middlewared.utils.tdb import close_sysdataset_tdb_handles
from middlewared.utils.zfs import query_imported_fast_impl


class SystemDatasetModel(sa.Model):
    __tablename__ = 'system_systemdataset'

    id = sa.Column(sa.Integer(), primary_key=True)
    sys_pool = sa.Column(sa.String(1024))
    sys_uuid = sa.Column(sa.String(32))
    sys_uuid_b = sa.Column(sa.String(32), nullable=True)


class SystemDatasetService(ConfigService):

    class Config:
        datastore = 'system.systemdataset'
        datastore_extend = 'systemdataset.config_extend'
        datastore_prefix = 'sys_'
        cli_namespace = 'system.system_dataset'
        role_prefix = 'DATASET'
        entry = SystemDatasetEntry

    force_pool = None

    @private
    def sysdataset_path(self, expected_datasetname=None):
        """
        This function returns either None or SYSDATASET_PATH,
        and is called potentially quite frequently (once per ZFS event
        or pool.dataset.query, etc).

        Best case scenario we have one cache lookup and one statvfs() call.
        Worst case, a mount_info lookup is added to the mix.

        `None` indicates that there was an issue with filesystem mounted
        at SYSDATASET_PATH. Typically this could indicate a failed migration
        of system dataset or problem importing expected pool for system dataset.

        Heuristic for wrong path is to first check result we cached from last time
        we checked the past. If dataset name matches, then perform an statvfs() on
        SYSDATASET_PATH to verify that the FSID matches.

        If we lack a cache entry, then look up SYSDATASET_PATH in mountinfo
        and make sure the two match. If they don't None is returned.

        If the mountinfo and expected value match, cache fsid and dataset name.
        """
        if expected_datasetname is None:
            db_pool = self.middleware.call_sync(
                'datastore.config',
                'system.systemdataset'
            )['sys_pool']
            pool = self.force_pool or db_pool or self.middleware.call_sync('boot.pool_name')
            ds_name = f'{pool}/.system'
        else:
            ds_name = expected_datasetname

        try:
            mntinfo = statmount(path=SYSDATASET_PATH)
        except FileNotFoundError:
            self.logger.warning('%s: mountpoint not found', SYSDATASET_PATH)
            return None

        if mntinfo['mount_source'] != ds_name:
            self.logger.warning('Unexpected dataset mounted at %s, %r present, but %r expected',
                                SYSDATASET_PATH, mntinfo['mount_source'], ds_name)
            return None

        return SYSDATASET_PATH

    @private
    async def config_extend(self, config):
        # Treat empty system dataset pool as boot pool
        config['pool_set'] = bool(config['pool'])
        config['pool'] = self.force_pool or config['pool'] or await self.middleware.call('boot.pool_name')

        config['basename'] = f'{config["pool"]}/.system'

        # Make `uuid` point to the uuid of current node
        uuid_key = 'uuid'
        if await self.middleware.call('failover.node') == 'B':
            uuid_key = 'uuid_b'
            config['uuid'] = config['uuid_b']

        del config['uuid_b']

        if not config['uuid']:
            config['uuid'] = uuid.uuid4().hex
            await self.middleware.call(
                'datastore.update', 'system.systemdataset', config['id'], {uuid_key: config['uuid']}, {'prefix': 'sys_'}
            )

        config['path'] = await self.middleware.run_in_thread(self.sysdataset_path, config['basename'])
        return config

    @private
    async def ensure_standby_uuid(self):
        remote_uuid_key = 'uuid_b'
        if await self.middleware.call('failover.node') == 'B':
            remote_uuid_key = 'uuid'

        local_config = await self.middleware.call('datastore.config', 'system.systemdataset', {'prefix': 'sys_'})
        if local_config[remote_uuid_key]:
            self.logger.debug('We already know the standby controller system dataset UUID')
            return

        remote_config = await self.middleware.call(
            'failover.call_remote', 'datastore.config', ['system.systemdataset', {'prefix': 'sys_'}],
        )
        if not remote_config[remote_uuid_key]:
            self.logger.warning('Standby controller does not yet have the system dataset UUID')
            return

        self.logger.info(f'Setting {remote_uuid_key}={remote_config[remote_uuid_key]!r}')
        await self.middleware.call(
            'datastore.update',
            'system.systemdataset',
            local_config['id'],
            {remote_uuid_key: remote_config[remote_uuid_key]},
            {'prefix': 'sys_'},
        )

    @private
    async def is_boot_pool(self):
        pool = (await self.config())['pool']
        if not pool:
            raise CallError('System dataset pool is not set. This may prevent '
                            'system services from functioning properly.')

        return pool in BOOT_POOL_NAME_VALID

    @api_method(SystemDatasetPoolChoicesArgs, SystemDatasetPoolChoicesResult, roles=['POOL_READ'])
    async def pool_choices(self, include_current_pool):
        """
        Retrieve pool choices which can be used for configuring system dataset.
        """
        boot_pool = await self.middleware.call('boot.pool_name')
        current_pool = (await self.config())['pool']
        valid_pools = await self.middleware.call(
            'systemdataset.query_pools_for_system_dataset'
        )

        pools = [boot_pool]
        if include_current_pool:
            pools.append(current_pool)
        pools.extend(valid_pools)

        return {
            p: p for p in sorted(set(pools))
        }

    @api_method(SystemDatasetUpdateArgs, SystemDatasetUpdateResult)
    @job(lock='sysdataset_update')
    async def do_update(self, job, data):
        """
        Update System Dataset Service Configuration.
        """
        data.setdefault('pool_exclude', None)
        config = await self.config()
        old_pool = config['pool']

        new_pool = await self._validate_and_select_pool(data, config)

        await self.middleware.call(
            'datastore.update',
            'system.systemdataset',
            config['id'],
            {'pool': new_pool},
            {'prefix': 'sys_'}
        )

        await self.middleware.call('systemdataset.setup', data['pool_exclude'])

        if await self.middleware.call('failover.licensed'):
            if await self.middleware.call('failover.status') == 'MASTER':
                try:
                    await self.middleware.call(
                        'failover.call_remote',
                        'system.reboot',
                        ['Failover system dataset change'],
                    )
                except Exception as e:
                    self.logger.debug(
                        'Failed to reboot standby storage controller after system dataset change: %s',
                        e
                    )

        return await self.config()

    async def _validate_and_select_pool(self, data, config):
        """Validate new pool selection and return final pool choice"""
        verrors = ValidationErrors()
        new_pool = data.get('pool', config['pool'])

        # Check if pool change is allowed
        if new_pool != config['pool']:
            system_ready = await self.middleware.call('system.ready')
            ds = await self.middleware.call('directoryservices.status')
            if system_ready and ds['type'] == DSType.AD.value and ds['status'] == DSStatus.HEALTHY.name:
                verrors.add(
                    'sysdataset_update.pool',
                    'System dataset location may not be moved while the Active Directory service is enabled.',
                    errno.EPERM
                )

            if new_pool:
                if error := await self.destination_pool_error(new_pool):
                    verrors.add('sysdataset_update.pool', error)

        # Validate pool choice if provided
        if new_pool:
            if new_pool not in await self.pool_choices(False):
                verrors.add(
                    'sysdataset_update.pool',
                    'The system dataset cannot be placed on this pool.'
                )

        verrors.check()
        return new_pool

    @private
    async def destination_pool_error(self, new_pool):
        config = await self.config()
        existing_dataset, new_dataset = None, None
        for i in await self.middleware.call(
            'zfs.resource.query_impl',
            {'paths': [config['basename'], new_pool], 'properties': ['used', 'available']}
        ):
            if i['name'] == config['basename']:
                existing_dataset = i
            elif i['name'] == new_pool:
                new_dataset = i

        if not existing_dataset:
            return
        elif not new_dataset:
            return f'Dataset {new_pool} does not exist'
        else:
            used = existing_dataset['properties']['used']['value']
            available = new_dataset['properties']['available']['value']

        # 1.1 is a safety margin because same files won't
        # take exactly the same amount of space on a different pool
        used = int(used * 1.1)
        if available < used:
            return (
                f'Insufficient disk space available on {new_pool} ({format_size(available)}). '
                f'Need {format_size(used)}'
            )

    @private
    def setup(self, exclude_pool: str | None = None):
        self.middleware.call_hook_sync('sysdataset.setup', data={'in_progress': True})
        try:
            return self.setup_impl(exclude_pool)
        finally:
            self.middleware.call_hook_sync('sysdataset.setup', data={'in_progress': False})

    @private
    def setup_impl(self, exclude_pool):
        """
        Internal implementation of setup - no recursion, clear flow.
        """
        self.force_pool = None
        config = self.middleware.call_sync('systemdataset.config')

        # Determine which pool to use
        target_pool, is_fallback = self.select_system_dataset_pool(
            preferred_pool=config['pool'],
            exclude_pool=exclude_pool
        )

        # If we selected a different pool than configured AND it's not a fallback,
        # update the database directly
        if target_pool != config['pool'] and not is_fallback:
            self.logger.info('Updating system dataset pool from %r to %r', config['pool'], target_pool)
            self.middleware.call_sync(
                'datastore.update',
                'system.systemdataset',
                config['id'],
                {'pool': target_pool},
                {'prefix': 'sys_'}
            )
            # Refresh config after database update
            config = self.middleware.call_sync('systemdataset.config')

        # If it's a temporary fallback, set force_pool so systemdataset.config returns the temporary pool
        if is_fallback:
            self.force_pool = target_pool
            config = self.middleware.call_sync('systemdataset.config')

        if not os.path.isdir(SYSDATASET_PATH) and os.path.exists(SYSDATASET_PATH):
            os.unlink(SYSDATASET_PATH)

        os.makedirs(SYSDATASET_PATH, mode=0o755, exist_ok=True)

        try:
            sysds_mntinfo = statmount(path=SYSDATASET_PATH)
            mounted_pool = sysds_mntinfo['mount_source'].split('/')[0]
        except FileNotFoundError:
            mounted_pool = None

        # If wrong pool is mounted, migrate
        if mounted_pool and mounted_pool != target_pool:
            self.logger.info('Migrating system dataset from %r to %r', mounted_pool, target_pool)
            self.migrate(mounted_pool, target_pool)
            return self.middleware.call_sync('systemdataset.config')

        # If nothing mounted or same pool, just ensure and mount
        datasets = self.middleware.call_sync('systemdataset.setup_datasets', target_pool, config['uuid'])

        if not mounted_pool:
            self.mount_system_dataset(datasets)

        # Post-mount setup
        self._post_mount_setup()

        return self.middleware.call_sync('systemdataset.config')

    @private
    def query_pools_for_system_dataset(self, exclude_pool=None):
        """
        Pools with passphrase-locked root level datasets are permitted as system
        dataset targets. This is because ZFS encryption is at the dataset level
        rather than pool level, and we use a legacy mount for the system dataset.
        Key format is only exposed via libzfs and so reading mountinfo here is
        insufficient.
        """
        rv = list()
        for i in query_imported_fast_impl().values():
            if (
                exclude_pool and exclude_pool == i['name']
                or i['name'] in BOOT_POOL_NAME_VALID
            ):
                continue

            ds = self.middleware.call_sync(
                'zfs.resource.query_impl',
                {'paths': [i['name']], 'properties': ['encryption']}
            )
            if not ds:
                continue

            enc = get_encryption_info(ds[0]['properties'])
            if not enc.encrypted or not enc.locked or enc.encryption_type == 'passphrase':
                rv.append(i['name'])
        return rv

    @private
    def select_system_dataset_pool(self, preferred_pool=None, exclude_pool=None):
        """
        Determine which pool should host the system dataset.
        Returns: (pool_name, is_temporary_fallback)

        Priority:
        1. preferred_pool (if valid and available)
        2. First available non-boot data pool (if not excluded)
        3. Boot pool (fallback)
        """
        boot_pool = self.middleware.call_sync('boot.pool_name')

        # Try preferred pool first
        if preferred_pool and preferred_pool != exclude_pool:
            if self._pool_is_available(preferred_pool):
                return (preferred_pool, False)

            # Pool encrypted/locked/missing - temporary fallback
            if preferred_pool != boot_pool:
                self.logger.warning('Pool %r unavailable, using boot pool temporarily', preferred_pool)
                return (boot_pool, True)

        # Find first available data pool
        for pool in self.query_pools_for_system_dataset(exclude_pool):
            return (pool, False)

        # Fallback to boot pool
        return (boot_pool, False)

    def _pool_is_available(self, pool):
        """Check if pool is mounted and unlocked"""
        boot_pool = self.middleware.call_sync('boot.pool_name')

        if pool == boot_pool:
            return True

        pool_mounted = any(
            mnt['mount_source'] == pool
            for mnt in iter_mountinfo()
        )

        if not pool_mounted:
            # Check if dataset exists and is encrypted/locked
            ds = self.middleware.call_sync(
                'zfs.resource.query_impl',
                {'paths': [pool], 'properties': ['encryption']}
            )
            if ds:
                enc = get_encryption_info(ds[0]['properties'])
                if enc.encrypted and enc.locked and enc.encryption_type != 'passphrase':
                    return False
            return False

        return True

    @private
    async def setup_datasets(self, pool, uuid):
        """
        Make sure system datasets for `pool` exist and have the right mountpoint property

        Returns datasets spec dict for the pool that will be used to construct mount tree
        """
        boot_pool = await self.middleware.call('boot.pool_name')
        # We may pass empty string for case where we don't have a valid data pool choice.
        # In this case fallback to boot pool.
        pool = pool or boot_pool
        root_dataset_is_passphrase_encrypted = False
        if pool != boot_pool:
            p = await self.middleware.call(
                'zfs.resource.query_impl',
                {'paths': [pool], 'properties': ['encryption']}
            )
            if not p:
                raise ValidationError(
                    'sysdataset_setup_datasets.pool',
                    f'Pool {pool!r} does not exist.',
                    errno.ENOENT,
                )
            else:
                enc = get_encryption_info(p[0]['properties'])
                root_dataset_is_passphrase_encrypted = enc.encryption_type == 'passphrase'

        datasets = {i['name']: i for i in get_system_dataset_spec(pool, uuid)}
        datasets_prop = {
            i['name']: i['properties']
            for i in await self.middleware.call(
                'zfs.resource.query_impl',
                {
                    'paths': list(datasets),
                    'properties': ['encryption', 'quota', 'used', 'mountpoint', 'readonly', 'snapdir', 'canmount']
                }
            )
        }
        for dataset, config in datasets.items():
            props = config['props']
            # Disable encryption for system managed datasets that are
            # configured on zpools that are passphrase-encrypted.
            if root_dataset_is_passphrase_encrypted:
                props['encryption'] = 'off'
            is_cores_ds = dataset.endswith('/cores')
            if is_cores_ds:
                props['quota'] = '1G'
            if dataset not in datasets_prop:
                await self.middleware.call(
                    'pool.dataset.create_impl', CreateImplArgs(name=dataset, ztype='FILESYSTEM', zprops=props)
                )
            elif is_cores_ds and datasets_prop[dataset]['used']['value'] >= 1024 ** 3:
                try:
                    await self.call2(self.s.zfs.resource.destroy_impl, dataset, recursive=True)
                    await self.middleware.call(
                        'pool.dataset.create_impl', CreateImplArgs(name=dataset, ztype='FILESYSTEM', zprops=props)
                    )
                except Exception:
                    self.logger.warning("Failed to replace dataset [%s].", dataset, exc_info=True)
            else:
                update_props_dict = dict()
                for k, v in props.items():
                    if datasets_prop[dataset][k]['raw'] != v:
                        # use `raw` key instead of `value` since
                        # the latter will do some fancy translation
                        # depending on the property.
                        # (i.e. if raw == "on" value == True)
                        update_props_dict[k] = v

                if update_props_dict:
                    await self.middleware.call(
                        'pool.dataset.update_impl',
                        UpdateImplArgs(name=dataset, zprops=update_props_dict)
                    )

        return list(datasets.values())

    def __create_relevant_paths(self, ds_name, create_paths):
        for create_path_config in create_paths:
            try:
                os.makedirs(create_path_config['path'], exist_ok=True)
                cpath_stat = os.stat(create_path_config['path'])
                if all(create_path_config[k] for k in ('uid', 'gid')) and (
                    cpath_stat.st_uid != create_path_config['uid'] or cpath_stat.st_gid != create_path_config['gid']
                ):
                    os.chown(create_path_config['path'], create_path_config['uid'], create_path_config['gid'])

                if (mode := create_path_config.get('mode')) and (cpath_stat.st_mode & 0o777) != mode:
                    os.chmod(create_path_config['path'], mode)
            except Exception:
                self.logger.exception(
                    'Failed to ensure %r path for %r dataset', create_path_config['path'], ds_name,
                )

    @private
    def apply_dataset_spec(self, datasets):
        for ds_config in datasets:
            self.__create_relevant_paths(ds_config['name'], ds_config.get('create_paths', []))
            self.__post_mount_actions(ds_config['name'], ds_config.get('post_mount_actions', []))

    def __post_mount_actions(self, ds_name, actions):
        for action in actions:
            try:
                self.middleware.call_sync(action['method'], *action.get('args', []))
            except Exception:
                self.logger.error(
                    'Failed to run post mount action %r endpoint for %r dataset',
                    action['method'], ds_name, exc_info=True,
                )
            else:
                self.logger.info(
                    'Successfully ran post mount action %r endpoint for %r dataset', action['method'], ds_name
                )

    @private
    def mount_system_dataset(self, datasets, target_path=SYSDATASET_PATH):
        """
        Mount system dataset hierarchy at target path.
        Applies permissions and runs post-mount actions.
        """
        target_fd = os.open(target_path, os.O_DIRECTORY)
        try:
            mount_hierarchy(target_fd=target_fd, datasets=datasets)
        finally:
            os.close(target_fd)

        self.apply_dataset_spec(datasets)

    def _rsync_system_dataset(self, from_path, to_path):
        """Rsync system dataset contents"""
        cp = subprocess.run(
            ['rsync', '-az', f'{from_path}/', to_path],
            check=False,
            capture_output=True
        )
        if cp.returncode != 0:
            raise CallError(f'Failed to rsync from {from_path}: {cp.stderr.decode()}')

    def _atomic_remount_sysdataset(self, new_path):
        """Atomically replace old mount with new mount"""
        # Get handle to new tree
        tmptree = truenas_os.open_tree(
            path=new_path,
            flags=truenas_os.AT_EMPTY_PATH|truenas_os.OPEN_TREE_CLOEXEC
        )

        try:
            try:
                truenas_os.move_mount(
                    from_dirfd=tmptree,
                    from_path="",
                    to_path=SYSDATASET_PATH,
                    flags=truenas_os.MOVE_MOUNT_F_EMPTY_PATH|truenas_os.MOVE_MOUNT_BENEATH
                )
            except Exception:
                self.logger.error('Failed to move %s to new path %s', SYSDATASET_PATH, new_path, exc_info=True)
            else:
                # succeed in move so unmount top layer
                old_stat = truenas_os.statx(path=SYSDATASET_PATH, mask=truenas_os.STATX_MNT_ID_UNIQUE)
                mnt_id = old_stat.stx_mnt_id
                for mnt in iter_mountinfo(target_mnt_id=mnt_id):
                    truenas_os.umount2(target=mnt['mountpoint'], flags=truenas_os.MNT_DETACH|truenas_os.MNT_FORCE)

                # Now unmount original
                truenas_os.umount2(target=SYSDATASET_PATH, flags=truenas_os.MNT_DETACH|truenas_os.MNT_FORCE)
                self._restart_dependent_services()

        finally:
            os.close(tmptree)

    def _post_mount_setup(self):
        """Post-mount setup: coredump bind mount, ACL disable, etc."""
        config = self.middleware.call_sync('systemdataset.config')

        # Verify correct pool is mounted
        sysds_mntinfo = statmount(path=SYSDATASET_PATH)
        mounted_pool = sysds_mntinfo['mount_source'].split('/')[0]

        if mounted_pool != config['pool']:
            raise CallError(
                f'{mounted_pool}: system dataset pool incorrect after remount. '
                f'Expected {config["pool"]}'
            )

        # Disable ACLs if enabled
        acl_enabled = (
            'POSIXACL' in sysds_mntinfo['super_opts'] or
            'NFSV4ACL' in sysds_mntinfo['super_opts']
        )
        if acl_enabled:
            self.middleware.call_sync(
                'pool.dataset.update_impl',
                UpdateImplArgs(name=config['basename'], zprops={'acltype': 'off'})
            )

        # Setup coredump bind mount
        corepath = f'{SYSDATASET_PATH}/cores'
        if os.path.exists(corepath):
            if self.middleware.call_sync('keyvalue.get', 'run_migration', False):
                try:
                    cores = Path(corepath)
                    for corefile in cores.iterdir():
                        corefile.unlink()
                except Exception:
                    self.logger.warning("Failed to clear old core files.", exc_info=True)

            truenas_os.umount2(target='/var/lib/systemd/coredump', flags=truenas_os.MNT_DETACH)
            os.makedirs('/var/lib/systemd/coredump', exist_ok=True)
            clone_fd = truenas_os.open_tree(
                path=corepath,
                flags=truenas_os.OPEN_TREE_CLONE | truenas_os.OPEN_TREE_CLOEXEC
            )
            try:
                truenas_os.move_mount(
                    from_dirfd=clone_fd,
                    from_path='',
                    to_path='/var/lib/systemd/coredump',
                    flags=truenas_os.MOVE_MOUNT_F_EMPTY_PATH
                )
            finally:
                os.close(clone_fd)

    def _restart_dependent_services(self):
        """Restart services that depend on system dataset"""
        restart = ['netdata']
        if self.middleware.call_sync('service.started', 'nfs'):
            restart.append('nfs')
        if self.middleware.call_sync('service.started', 'cifs'):
            restart.insert(0, 'cifs')
        if self.middleware.call_sync('service.started', 'open-vm-tools'):
            restart.append('open-vm-tools')

        close_sysdataset_tdb_handles()
        for svc in restart:
            self.middleware.call_sync('service.control', 'RESTART', svc).wait_sync(raise_error=True)

    def _migrate_with_data_copy(self, from_pool, to_pool, datasets):
        """Perform migration with data copy and atomic remount"""
        with tempfile.TemporaryDirectory(prefix='/var/db/', ignore_cleanup_errors=True) as tmpdir:
            # Mount new datasets in temp location
            tmptarget_fd = os.open(tmpdir, os.O_DIRECTORY)
            os.fchmod(tmptarget_fd, 0o700)

            try:
                mount_hierarchy(target_fd=tmptarget_fd, datasets=datasets)

                # Copy data
                self._rsync_system_dataset(SYSDATASET_PATH, tmpdir)

                # Atomic switcheroo
                self._atomic_remount_sysdataset(tmpdir)

            finally:
                os.close(tmptarget_fd)

                # Check if tmpdir is still a mount point (only on error path)
                tmpdir_stat = truenas_os.statx(
                    path=tmpdir,
                    mask=truenas_os.STATX_MNT_ID_UNIQUE | truenas_os.STATX_BASIC_STATS
                )
                if tmpdir_stat.stx_attributes & truenas_os.STATX_ATTR_MOUNT_ROOT:
                    # Still mounted, so we're on error path - unmount children
                    tmpdir_mnt_id = tmpdir_stat.stx_mnt_id
                    for mnt in iter_mountinfo(target_mnt_id=tmpdir_mnt_id):
                        truenas_os.umount2(target=mnt['mountpoint'], flags=truenas_os.MNT_DETACH|truenas_os.MNT_FORCE)

                    # Now unmount original
                    truenas_os.umount2(target=tmpdir, flags=truenas_os.MNT_DETACH|truenas_os.MNT_FORCE)

    @private
    def migrate(self, _from, _to):
        """
        Migrate system dataset from one pool to another.
        Copies data and atomically switches mount points.
        """
        config = self.middleware.call_sync('systemdataset.config')
        os.makedirs(SYSDATASET_PATH, mode=0o755, exist_ok=True)

        # Ensure target datasets exist
        datasets = self.middleware.call_sync('systemdataset.setup_datasets', _to, config['uuid'])

        # Simple case: nothing to migrate, just mount
        if not _from:
            self.mount_system_dataset(datasets)
            self._post_mount_setup()
            return

        # Complex case: need to migrate data
        self._migrate_with_data_copy(_from, _to, datasets)

        # Post-migration setup
        self._post_mount_setup()

    @private
    def get_system_dataset_spec(self, pool, uid):
        return get_system_dataset_spec(pool, uid)


async def pool_post_create(middleware, pool):
    if (await middleware.call('systemdataset.config'))['pool'] == await middleware.call('boot.pool_name'):
        await middleware.call('systemdataset.setup')


async def pool_post_import(middleware, pool):
    """
    On pool import we may need to reconfigure system dataset.
    """
    await middleware.call('systemdataset.setup')


async def pool_pre_export(middleware, pool, options, job):
    sysds = await middleware.call('systemdataset.config')
    if sysds['pool'] == pool:
        job.set_progress(40, 'Reconfiguring system dataset')
        sysds_job = await middleware.call('systemdataset.update', {
            'pool': None, 'pool_exclude': pool,
        })
        await sysds_job.wait()
        if sysds_job.error:
            raise CallError(f'This pool contains system dataset, but its reconfiguration failed: {sysds_job.error}')


async def setup(middleware):
    def setup_paths():
        os.makedirs(SYSDATASET_PATH, mode=0o755, exist_ok=True)
        truenas_os.mount_setattr(path='/var', propagation=truenas_os.MS_PRIVATE, flags=truenas_os.AT_RECURSIVE)
        if not os.path.exists('/var/cache/nscd') or not os.path.islink('/var/cache/nscd'):
            if os.path.exists('/var/cache/nscd'):
                shutil.rmtree('/var/cache/nscd')

            os.makedirs('/var/run/nscd/cache', exist_ok=True)

        if not os.path.islink('/var/cache/nscd'):
            os.symlink('/var/run/nscd/cache', '/var/cache/nscd')

    middleware.register_hook('pool.post_create', pool_post_create)
    # Reconfigure system dataset first thing after we import a pool.
    middleware.register_hook('pool.post_import', pool_post_import, order=-10000)
    middleware.register_hook('pool.pre_export', pool_pre_export, order=40, raise_error=True)

    try:
        await middleware.run_in_thread(setup_paths)
    except Exception:
        middleware.logger.error('Error moving cache away from boot pool', exc_info=True)
