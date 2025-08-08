import errno
import json
import os
import shutil
import subprocess
import threading
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
from middlewared.plugins.system_dataset.utils import SYSDATASET_PATH
from middlewared.plugins.zfs.utils import get_encryption_info
from middlewared.service import CallError, ConfigService, ValidationErrors, job, private
from middlewared.utils import filter_list, MIDDLEWARE_RUN_DIR, BOOT_POOL_NAME_VALID
from middlewared.utils.directoryservices.constants import DSStatus, DSType
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
    sysdataset_release_lock = threading.Lock()

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
            cached_entry = self.middleware.call_sync('cache.get', 'SYSDATASET_PATH')
        except KeyError:
            cached_entry = None

        try:
            fsid = os.statvfs(SYSDATASET_PATH).f_fsid
        except FileNotFoundError:
            # SYSDATASET_PATH may not exist on first boot. Do not log.
            return None
        except OSError:
            self.logger.warning('Failed to stat sysdataset fd', exc_info=True)
            return None

        if cached_entry and cached_entry['dataset'] == ds_name:
            if fsid == cached_entry['fsid']:
                return SYSDATASET_PATH

        mntinfo = self.middleware.call_sync(
            'filesystem.mount_info',
            [['mountpoint', '=', SYSDATASET_PATH]]
        )
        if not mntinfo:
            self.logger.warning('%s: mountpoint not found', SYSDATASET_PATH)
            return None

        if mntinfo[0]['mount_source'] != ds_name:
            self.logger.warning('Unexpected dataset mounted at %s, %r present, but %r expected. fsid: %d',
                                SYSDATASET_PATH, mntinfo[0]['mount_source'], ds_name, fsid)
            return None

        self.middleware.call_sync('cache.put', 'SYSDATASET_PATH', {'dataset': ds_name, 'fsid': fsid})
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

        new = config.copy()
        new.update(data)

        verrors = ValidationErrors()
        if new['pool'] != config['pool']:
            system_ready = await self.middleware.call('system.ready')
            ds = await self.middleware.call('directoryservices.status')
            if system_ready and ds['type'] == DSType.AD.value and ds['status'] == DSStatus.HEALTHY.name:
                verrors.add(
                    'sysdataset_update.pool',
                    'System dataset location may not be moved while the Active Directory service is enabled.',
                    errno.EPERM
                )

            if new['pool']:
                if error := await self.destination_pool_error(new['pool']):
                    verrors.add('sysdataset_update.pool', error)

        if new['pool']:
            if new['pool'] not in await self.pool_choices(False):
                verrors.add(
                    'sysdataset_update.pool',
                    'The system dataset cannot be placed on this pool.'
                )
        else:
            for pool in await self.middleware.call(
                'systemdataset.query_pools_for_system_dataset', data['pool_exclude']
            ):
                if await self.destination_pool_error(pool):
                    continue

                new['pool'] = pool
                break
            else:
                # If a data pool could not be found, reset it to blank
                # Which will eventually mean its back to boot pool (temporarily)
                new['pool'] = ''

        verrors.check()

        update_dict = {k: v for k, v in new.items() if k in ['pool']}

        await self.middleware.call(
            'datastore.update',
            'system.systemdataset',
            config['id'],
            update_dict,
            {'prefix': 'sys_'}
        )

        new = await self.config()

        if config['pool'] != new['pool']:
            await self.middleware.call('systemdataset.migrate', config['pool'], new['pool'])

        await self.middleware.call('systemdataset.setup', data['pool_exclude'])

        if await self.middleware.call('failover.licensed'):
            if await self.middleware.call('failover.status') == 'MASTER':
                try:
                    await self.middleware.call(
                        'failover.call_remote', 'system.reboot', ['Failover system dataset change'],
                    )
                except Exception as e:
                    self.logger.debug('Failed to reboot standby storage controller after system dataset change: %s', e)

        return await self.config()

    @private
    async def destination_pool_error(self, new_pool):
        config = await self.config()
        existing_dataset = await self.middleware.call(
            'zfs.resource.query_impl', {'paths': [config['basename']], 'properties': ['used']}
        )
        if not existing_dataset:
            return
        else:
            used = existing_dataset[0]['properties']['used']['value']

        new_dataset = await self.middleware.call(
            'zfs.resource.query_impl', {'paths': [new_pool], 'properties': ['available']}
        )
        if not new_dataset:
            return f'Dataset {new_pool} does not exist'
        else:
            available = new_dataset[0]['properties']['available']['value']

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
        self.force_pool = None
        config = self.middleware.call_sync('systemdataset.config')

        boot_pool = self.middleware.call_sync('boot.pool_name')

        # If the system dataset is configured in a data pool we need to make sure it exists.
        # In case it does not we need to use another one.
        filters = [('name', '=', config['pool'])]
        if config['pool'] != boot_pool and not self.middleware.call_sync('pool.query', filters):
            self.logger.debug('Pool %r does not exist, moving system dataset to another pool', config['pool'])
            job = self.middleware.call_sync('systemdataset.update', {'pool': None, 'pool_exclude': exclude_pool})
            job.wait_sync()
            if job.error:
                raise CallError(job.error)
            return

        # If we dont have a pool configured in the database try to find the first data pool
        # to put it on.
        if not config['pool_set']:
            if pools := self.query_pools_for_system_dataset(exclude_pool):
                self.logger.debug(
                    'System dataset pool was not set, moving it to first available pool %r',
                    pools[0]
                )
                job = self.middleware.call_sync('systemdataset.update', {'pool': pools[0]})
                job.wait_sync(raise_error=True)
                return

        mntinfo = self.middleware.call_sync('filesystem.mount_info')
        if config['pool'] != boot_pool:
            if not any(filter_list(mntinfo, [['mount_source', '=', config['pool']]])):
                ds = self.middleware.call_sync(
                    'zfs.resource.query_impl',
                    {'paths': [config['basename']], 'properties': ['encryption']}
                )
                if not ds:
                    # Pool is not mounted (e.g. HA node B), temporary set up system dataset on the boot pool
                    msg = 'Root dataset for pool %r is not available, and dataset %r does not exist, '
                    msg += 'temporarily setting up system dataset on boot pool'
                    self.logger.debug(msg, config['pool'], config['basename'])
                    self.force_pool = boot_pool
                    config = self.middleware.call_sync('systemdataset.config')
                enc = get_encryption_info(ds[0]['properties'])
                if enc.encrypted and enc.locked and enc.encryption_type != 'passphrase':
                    # Pool is encrypted with a key and is locked
                    self.logger.debug(
                        'Root dataset for pool %r is not available, temporarily setting up system dataset on boot pool',
                        config['pool'],
                    )
                    self.force_pool = boot_pool
                    config = self.middleware.call_sync('systemdataset.config')
                else:
                    self.logger.debug(
                        'Root dataset for pool %r is not available, but system dataset may be manually '
                        'mounted. Proceeding with normal setup.',
                        config['pool']
                    )

        mounted_pool = mounted = None

        sysds_mntinfo = filter_list(mntinfo, [['mountpoint', '=', '/var/db/system']])
        if sysds_mntinfo:
            mounted_pool = sysds_mntinfo[0]['mount_source'].split('/')[0]

        if mounted_pool and mounted_pool.split('/')[0] != config['pool']:
            self.logger.debug('Abandoning dataset on %r in favor of %r', mounted_pool, config['pool'])
            with self.release_system_dataset():
                self.__umount(mounted_pool, config['uuid'])
                self.middleware.call_sync('systemdataset.setup_datasets', config['pool'], config['uuid'])
                mounted = self.__mount(config['pool'], config['uuid'])
        else:
            self.middleware.call_sync('systemdataset.setup_datasets', config['pool'], config['uuid'])

        # refresh our mountinfo in case it changed
        mntinfo = self.middleware.call_sync('filesystem.mount_info')
        sysds_mntinfo = filter_list(mntinfo, [['mountpoint', "=", SYSDATASET_PATH]])

        if not os.path.isdir(SYSDATASET_PATH) and os.path.exists(SYSDATASET_PATH):
            os.unlink(SYSDATASET_PATH)

        os.makedirs(SYSDATASET_PATH, mode=0o755, exist_ok=True)

        ds_mntinfo = filter_list(mntinfo, [['mount_source', '=', config['basename']]])
        if ds_mntinfo:
            acl_enabled = 'POSIXACL' in ds_mntinfo[0]['super_opts'] or 'NFSV4ACL' in ds_mntinfo[0]['super_opts']
        else:
            ds = self.middleware.call_sync(
                'zfs.resource.query_impl',
                {'paths': [config['basename']], 'properties': ['acltype']}
            )
            acl_enabled = ds and ds[0]['properties']['acltype']['raw'] != 'off'

        if acl_enabled:
            self.middleware.call_sync(
                'zfs.dataset.update', config['basename'], {'properties': {'acltype': {'value': 'off'}}}
            )

        if mounted is None:
            mounted = self.__mount(config['pool'], config['uuid'])

        corepath = f'{SYSDATASET_PATH}/cores'
        if os.path.exists(corepath):
            if self.middleware.call_sync('keyvalue.get', 'run_migration', False):
                try:
                    cores = Path(corepath)
                    for corefile in cores.iterdir():
                        corefile.unlink()
                except Exception:
                    self.logger.warning("Failed to clear old core files.", exc_info=True)

            subprocess.run(['umount', '/var/lib/systemd/coredump'], check=False)
            os.makedirs('/var/lib/systemd/coredump', exist_ok=True)
            subprocess.run(['mount', '--bind', corepath, '/var/lib/systemd/coredump'])

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
        if exclude_pool:
            nf = [exclude_pool]
        else:
            nf = exclude_pool

        rv = list()
        for i in query_imported_fast_impl(name_filters=nf).values():
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
    async def setup_datasets(self, pool, uuid):
        """
        Make sure system datasets for `pool` exist and have the right mountpoint property
        """
        boot_pool = await self.middleware.call('boot.pool_name')
        root_dataset_is_passphrase_encrypted = (
            pool != boot_pool and
            (await self.middleware.call('pool.dataset.get_instance', pool))['key_format']['value'] == 'PASSPHRASE'
        )
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
            # Disable encryption for pools with passphrase-encrypted root datasets so that system dataset could be
            # automatically mounted on system boot.
            if root_dataset_is_passphrase_encrypted:
                props['encryption'] = 'off'
            is_cores_ds = dataset.endswith('/cores')
            if is_cores_ds:
                props['quota'] = '1G'
            if dataset not in datasets_prop:
                await self.middleware.call('zfs.dataset.create', {'name': dataset, 'properties': props})
            elif is_cores_ds and datasets_prop[dataset]['used']['value'] >= 1024 ** 3:
                try:
                    await self.middleware.call('zfs.dataset.delete', dataset, {'force': True, 'recursive': True})
                    await self.middleware.call('zfs.dataset.create', {'name': dataset, 'properties': props})
                except Exception:
                    self.logger.warning("Failed to replace dataset [%s].", dataset, exc_info=True)
            else:
                update_props_dict = {
                    k: {'value': v} for k, v in props.items()
                    # use `raw` key instead of `value` since
                    # the latter will do some fancy translation
                    # depending on the property.
                    # (i.e. if raw == "on" value == True)
                    if datasets_prop[dataset][k]['raw'] != v
                }
                if update_props_dict:
                    await self.middleware.call(
                        'zfs.dataset.update',
                        dataset,
                        {'properties': update_props_dict},
                    )

            try:
                await self.middleware.run_in_thread(self.__create_relevant_paths, config.get('create_paths', []))
            except Exception:
                self.logger.error('Failed to create relevant paths for %r', dataset, exc_info=True)

    def __create_relevant_paths(self, create_paths):
        for create_path_config in create_paths:
            os.makedirs(create_path_config['path'], exist_ok=True)
            cpath_stat = os.stat(create_path_config['path'])
            if all(create_path_config[k] for k in ('uid', 'gid')) and (
                cpath_stat.st_uid != create_path_config['uid'] or cpath_stat.st_gid != create_path_config['gid']
            ):
                os.chown(create_path_config['path'], create_path_config['uid'], create_path_config['gid'])

            if (mode := create_path_config.get('mode')) and (cpath_stat.st_mode & 0o777) != mode:
                os.chmod(create_path_config['path'], mode)

    def __mount(self, pool, uuid, path=SYSDATASET_PATH):
        """
        Mount group of datasets associated with our system dataset.
        `path` will be either  SYSDATASET_PATH or temp dir in the middlewared
        rundir. The latter occurs when migrating dataset between pools.
        """
        mounted = False
        for ds_config in get_system_dataset_spec(pool, uuid):
            dataset, name = ds_config['name'], os.path.basename(ds_config['name'])

            mountpoint = ds_config.get('mountpoint', f'{SYSDATASET_PATH}/{name}').replace(SYSDATASET_PATH, path)

            if os.path.ismount(mountpoint):
                continue

            with suppress(FileExistsError):
                os.mkdir(mountpoint)
            subprocess.run(['mount', '-t', 'zfs', dataset, mountpoint], check=True)

            chown_config = ds_config['chown_config']
            mode_perms = chown_config.pop('mode')
            mountpoint_stat = os.stat(mountpoint)
            if mountpoint_stat.st_uid != chown_config['uid'] or mountpoint_stat.st_gid != chown_config['gid']:
                os.chown(mountpoint, **chown_config)

            if (mountpoint_stat.st_mode & 0o777) != mode_perms:
                os.chmod(mountpoint, mode_perms)

            mounted = True
            if path == SYSDATASET_PATH:
                self.__post_mount_actions(ds_config['name'], ds_config.get('post_mount_actions', []))

        if mounted and path == SYSDATASET_PATH:
            fsid = os.statvfs(SYSDATASET_PATH).f_fsid
            self.middleware.call_sync('cache.put', 'SYSDATASET_PATH', {'dataset': f'{path}/.system', 'fsid': fsid})

        return mounted

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

    def __umount(self, pool, uuid, retry=True):
        """
        Umount the group of datasets associated with the system dataset.
        When migrating between system datasets, `pool` will be filesystem
        mounted in middleware rundir for one of the umount calls.

        This is why mount info is checked before manipulating sysdataset_path.
        """
        current = self.middleware.call_sync('filesystem.mount_info', [['mountpoint', '=', SYSDATASET_PATH]])
        if current and current[0]['mount_source'].split('/')[0] == pool:
            try:
                self.middleware.call_sync('cache.pop', 'SYSDATASET_PATH')
            except KeyError:
                pass

        mntinfo = self.middleware.call_sync(
            'filesystem.mount_info',
            [['mount_source', '=', f'{pool}/.system']]
        )
        if not mntinfo:
            # Pool's system dataset not mounted
            return

        mp = mntinfo[0]['mountpoint']
        if retry:
            flags = '-f' if not self.middleware.call_sync('failover.licensed') else '-l'
        else:
            # We're doing a retry and have logged a warning message pointing fingers
            # at offending processes so that a dev can hopefully fix it later on.
            flags = '-lf'

        try:
            subprocess.run(['umount', flags, '--recursive', mp], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode()
            if 'no mount point specified' in stderr:
                return
        else:
            return

        error = f'Unable to umount {mp}: {stderr}'
        if 'target is busy' in stderr:
            # error message is of format "umount: <mountpoint>: target is busy"
            ds_mp = stderr.split(':')[1].strip()
            processes = self.middleware.call_sync('pool.dataset.processes_using_paths', [ds_mp], True, True)

            if retry:
                self.logger.warning("The following processes are using %s: %s",
                                    ds_mp, json.dumps(processes, indent=2))
                return self.__umount(pool, uuid, False)

            error += f'\nThe following processes are using {ds_mp!r}: ' + json.dumps(processes, indent=2)

        raise CallError(error) from None

    @private
    def migrate(self, _from, _to):
        """
        Migrate system dataset to a new pool. If it is moving from
        an existing pool, then the new datasets are mounted in
        the middleware rundir temprorarily so that data can be
        rsynced from the old pool.
        """
        config = self.middleware.call_sync('systemdataset.config')

        os.makedirs(SYSDATASET_PATH, mode=0o755, exist_ok=True)
        self.middleware.call_sync('systemdataset.setup_datasets', _to, config['uuid'])

        if _from:
            path = f'{MIDDLEWARE_RUN_DIR}/system.new'
            if not os.path.exists(f'{MIDDLEWARE_RUN_DIR}/system.new'):
                os.mkdir(f'{MIDDLEWARE_RUN_DIR}/system.new')
            else:
                # Make sure we clean up any previous attempts
                subprocess.run(['umount', '-R', path], check=False)
        else:
            path = SYSDATASET_PATH

        self.__mount(_to, config['uuid'], path=path)

        # context manager handles service stop / restart
        with self.release_system_dataset():
            if _from:
                cp = subprocess.run(
                    ['rsync', '-az', f'{SYSDATASET_PATH}/', f'{MIDDLEWARE_RUN_DIR}/system.new'],
                    check=False,
                    capture_output=True
                )
                if cp.returncode == 0:
                    # Let's make sure that we don't have coredump directory mounted
                    subprocess.run(['umount', '/var/lib/systemd/coredump'], check=False)
                    self.__umount(_from, config['uuid'])
                    self.__umount(_to, config['uuid'])
                    self.__mount(_to, config['uuid'], SYSDATASET_PATH)
                    proc = subprocess.Popen(f'zfs list -H -o name {_from}/.system|xargs zfs destroy -r', shell=True)
                    proc.communicate()

                    os.rmdir(f'{MIDDLEWARE_RUN_DIR}/system.new')
                else:
                    raise CallError(f'Failed to rsync from {SYSDATASET_PATH}: {cp.stderr.decode()}')

    @contextmanager
    @private
    def release_system_dataset(self):
        """
        This context manager is used to toggle system-dataset dependent services and
        tasks for cases where the dataset is unmounted / remounted.

        The operations are performed under a lock because systemdataset.update() and
        systemdataset.setup() both can lead to this being called, and we don't want
        simultaneous releases of system dataset.
        """
        with self.sysdataset_release_lock:
            # TODO: Review these services because /var/log no longer sits on
            # the system dataset so any service that could potentially open
            # a file descriptor underneath /var/log will no longer need to be
            # stopped/restarted to allow the system dataset to migrate
            restart = ['netdata']
            if self.middleware.call_sync('service.started', 'nfs'):
                restart.append('nfs')
            if self.middleware.call_sync('service.started', 'cifs'):
                restart.insert(0, 'cifs')
            if self.middleware.call_sync('service.started', 'open-vm-tools'):
                restart.append('open-vm-tools')
            if self.middleware.call_sync('service.started', 'idmap'):
                restart.append('idmap')
            if self.middleware.call_sync('service.started', 'nmbd'):
                restart.append('nmbd')
            if self.middleware.call_sync('service.started', 'wsdd'):
                restart.append('wsdd')

            try:
                for i in restart:
                    self.middleware.call_sync('service.control', 'STOP', i).wait_sync(raise_error=True)

                close_sysdataset_tdb_handles()
                yield
            finally:
                restart.reverse()
                for i in restart:
                    self.middleware.call_sync('service.control', 'START', i).wait_sync(raise_error=True)

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
