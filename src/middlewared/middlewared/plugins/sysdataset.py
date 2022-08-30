from middlewared.schema import accepts, Bool, Dict, Int, returns, Str
from middlewared.service import CallError, ConfigService, ValidationErrors, job, private
from middlewared.service_exception import InstanceNotFound
import middlewared.sqlalchemy as sa
from middlewared.utils import Popen, run
from middlewared.utils.size import format_size
from middlewared.plugins.boot import BOOT_POOL_NAME_VALID

try:
    from middlewared.plugins.cluster_linux.utils import CTDBConfig
except ImportError:
    CTDBConfig = None

import asyncio
from contextlib import asynccontextmanager
import errno
import json
import os
from pathlib import Path
import psutil
import shutil
import subprocess
import uuid

SYSDATASET_PATH = '/var/db/system'


class SystemDatasetModel(sa.Model):
    __tablename__ = 'system_systemdataset'

    id = sa.Column(sa.Integer(), primary_key=True)
    sys_pool = sa.Column(sa.String(1024))
    sys_syslog_usedataset = sa.Column(sa.Boolean(), default=False)
    sys_uuid = sa.Column(sa.String(32))
    sys_uuid_b = sa.Column(sa.String(32), nullable=True)


class SystemDatasetService(ConfigService):

    class Config:
        datastore = 'system.systemdataset'
        datastore_extend = 'systemdataset.config_extend'
        datastore_prefix = 'sys_'
        cli_namespace = 'system.system_dataset'

    ENTRY = Dict(
        'systemdataset_entry',
        Int('id', required=True),
        Str('pool', required=True),
        Bool('pool_set', required=True),
        Str('uuid', required=True),
        Str('uuid_b', required=True, null=True),
        Str('basename', required=True),
        Str('uuid_a', required=True),
        Bool('syslog', required=True),
        Str('path', required=True, null=True),
    )

    force_pool = None

    @private
    async def config_extend(self, config):

        # Treat empty system dataset pool as boot pool
        config['pool_set'] = bool(config['pool'])
        config['pool'] = self.force_pool or config['pool'] or await self.middleware.call('boot.pool_name')

        config['basename'] = f'{config["pool"]}/.system'

        # Make `uuid` point to the uuid of current node
        config['uuid_a'] = config['uuid']
        is_enterprise = await self.middleware.call('system.is_enterprise')
        is_node_b = False
        if is_enterprise:
            if await self.middleware.call('failover.node') == 'B':
                is_node_b = True
                config['uuid'] = config['uuid_b']

        if not config['uuid']:
            config['uuid'] = uuid.uuid4().hex
            if is_enterprise and is_node_b:
                attr = 'uuid_b'
                config[attr] = config['uuid']
            else:
                attr = 'uuid'
            await self.middleware.call(
                'datastore.update', 'system.systemdataset', config['id'], {f'sys_{attr}': config['uuid']}
            )

        config['syslog'] = config.pop('syslog_usedataset')

        if not os.path.exists(SYSDATASET_PATH) or not os.path.ismount(SYSDATASET_PATH):
            config['path'] = None
        else:
            config['path'] = SYSDATASET_PATH

        return config

    @private
    async def is_boot_pool(self):
        pool = (await self.config())['pool']
        if not pool:
            raise CallError('System dataset pool is not set. This may prevent '
                            'system services from functioning properly.')

        return pool in BOOT_POOL_NAME_VALID

    @accepts(Bool('include_current_pool', default=True))
    @returns(Dict('systemdataset_pool_choices', additional_attrs=True))
    async def pool_choices(self, include_current_pool):
        """
        Retrieve pool choices which can be used for configuring system dataset.
        """
        boot_pool = await self.middleware.call('boot.pool_name')
        current_pool = (await self.config())['pool']
        valid_pools = await self._query_pools_names_for_system_dataset()

        pools = [boot_pool]
        if include_current_pool:
            pools.append(current_pool)
        pools.extend(valid_pools)

        return {
            p: p for p in sorted(set(pools))
        }

    @accepts(Dict(
        'sysdataset_update',
        Str('pool', null=True),
        Str('pool_exclude', null=True),
        Bool('syslog'),
        update=True
    ))
    @job(lock='sysdataset_update')
    async def do_update(self, job, data):
        """
        Update System Dataset Service Configuration.

        `pool` is the name of a valid pool configured in the system which will be used to host the system dataset.

        `pool_exclude` can be specified to make sure that we don't place the system dataset on that pool if `pool`
        is not provided.
        """
        data.setdefault('pool_exclude', None)

        config = await self.config()

        new = config.copy()
        new.update(data)

        verrors = ValidationErrors()
        if new['pool'] != config['pool']:
            system_ready = await self.middleware.call('system.ready')
            ad_enabled = (await self.middleware.call('activedirectory.get_state')) in ['HEALTHY', 'FAULTED']
            if system_ready and ad_enabled:
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
            for pool in await self._query_pools_names_for_system_dataset(data['pool_exclude']):
                if await self.destination_pool_error(pool):
                    continue

                new['pool'] = pool
                break
            else:
                # If a data pool could not be found, reset it to blank
                # Which will eventually mean its back to boot pool (temporarily)
                new['pool'] = ''

        verrors.check()

        new['syslog_usedataset'] = new['syslog']

        update_dict = new.copy()
        for key in ('basename', 'uuid_a', 'syslog', 'path', 'pool_exclude', 'pool_set'):
            update_dict.pop(key, None)

        await self.middleware.call(
            'datastore.update',
            'system.systemdataset',
            config['id'],
            update_dict,
            {'prefix': 'sys_'}
        )

        new = await self.config()

        if config['pool'] != new['pool']:
            await self.migrate(config['pool'], new['pool'])

        await self.setup(data['pool_exclude'])

        if config['syslog'] != new['syslog']:
            await self.middleware.call('service.restart', 'syslogd')

        if await self.middleware.call('failover.licensed'):
            if await self.middleware.call('failover.status') == 'MASTER':
                try:
                    await self.middleware.call('failover.call_remote', 'system.reboot')
                except Exception as e:
                    self.logger.debug('Failed to reboot standby storage controller after system dataset change: %s', e)

        return await self.config()

    @private
    async def destination_pool_error(self, new_pool):
        config = await self.config()

        try:
            existing_dataset = await self.middleware.call('zfs.dataset.get_instance', config['basename'])
        except InstanceNotFound:
            return

        used = existing_dataset['properties']['used']['parsed']

        try:
            new_dataset = await self.middleware.call('zfs.dataset.get_instance', new_pool)
        except InstanceNotFound:
            return f'Dataset {new_pool} does not exist'

        available = new_dataset['properties']['available']['parsed']

        # 1.1 is a safety margin because same files won't take exactly the same amount of space on a different pool
        used = int(used * 1.1)
        if available < used:
            return (
                f'Insufficient disk space available on {new_pool} ({format_size(available)}). '
                f'Need {format_size(used)}'
            )

    @accepts(Str('exclude_pool', default=None, null=True))
    @private
    async def setup(self, exclude_pool):
        self.force_pool = None
        config = await self.config()

        boot_pool = await self.middleware.call('boot.pool_name')

        # If the system dataset is configured in a data pool we need to make sure it exists.
        # In case it does not we need to use another one.
        filters = [('name', '=', config['pool'])]
        if config['pool'] != boot_pool and not await self.middleware.call('pool.query', filters):
            self.logger.debug('Pool %r does not exist, moving system dataset to another pool', config['pool'])
            job = await self.middleware.call('systemdataset.update', {'pool': None, 'pool_exclude': exclude_pool})
            await job.wait()
            if job.error:
                raise CallError(job.error)
            return

        # If we dont have a pool configured in the database try to find the first data pool
        # to put it on.
        if not config['pool_set']:
            if pool := await self._query_pool_for_system_dataset(exclude_pool):
                self.logger.debug('Sysdataset pool was not set, moving it to first available pool %r', pool['name'])
                job = await self.middleware.call('systemdataset.update', {'pool': pool['name']})
                await job.wait()
                if job.error:
                    raise CallError(job.error)
                return

        if config['pool'] != boot_pool:
            dataset = await self.middleware.call('pool.dataset.query', [['name', '=', config['pool']]],
                                                 {'extra': {'retrieve_children': False}})
            if not dataset or (dataset[0]['locked'] and dataset[0]['key_format']['value'] != 'PASSPHRASE'):
                # Pool is not mounted (e.g. HA node B), temporary set up system dataset on the boot pool
                self.logger.debug(
                    'Root dataset for pool %r is not available, temporarily setting up system dataset on boot pool',
                    config['pool'],
                )
                self.force_pool = boot_pool
                config = await self.config()

        mounted_pool = mounted = None
        for p in psutil.disk_partitions():
            if p.mountpoint == SYSDATASET_PATH:
                mounted_pool = p.device.split('/')[0]
        if mounted_pool and mounted_pool != config['pool']:
            self.logger.debug('Abandoning dataset on %r in favor of %r', mounted_pool, config['pool'])
            async with self._release_system_dataset():
                await self.__umount(mounted_pool, config['uuid'])
                await self.__setup_datasets(config['pool'], config['uuid'])
                mounted = await self.__mount(config['pool'], config['uuid'])
        else:
            await self.__setup_datasets(config['pool'], config['uuid'])

        if not os.path.isdir(SYSDATASET_PATH):
            if os.path.exists(SYSDATASET_PATH):
                os.unlink(SYSDATASET_PATH)
            os.makedirs(SYSDATASET_PATH)

        acltype = await self.middleware.call('zfs.dataset.query', [('id', '=', config['basename'])])
        if acltype and acltype[0]['properties']['acltype']['value'] != 'off':
            await self.middleware.call(
                'zfs.dataset.update', config['basename'], {'properties': {'acltype': {'value': 'off'}}}
            )

        if mounted is None:
            mounted = await self.__mount(config['pool'], config['uuid'])

        corepath = f'{SYSDATASET_PATH}/cores'
        if os.path.exists(corepath):
            os.chmod(corepath, 0o775)

            if await self.middleware.call('keyvalue.get', 'run_migration', False):
                try:
                    cores = Path(corepath)
                    for corefile in cores.iterdir():
                        corefile.unlink()
                except Exception:
                    self.logger.warning("Failed to clear old core files.", exc_info=True)

            await run('umount', '/var/lib/systemd/coredump', check=False)
            os.makedirs('/var/lib/systemd/coredump', exist_ok=True)
            await run('mount', '--bind', corepath, '/var/lib/systemd/coredump')

        await self.middleware.call('etc.generate', 'glusterd')

        if mounted:
            await self.middleware.call('smb.setup_directories')

            # There is no need to wait this to finish
            # Restarting rrdcached will ensure that we start/restart collectd as well
            asyncio.ensure_future(self.middleware.call('service.restart', 'rrdcached'))
            asyncio.ensure_future(self.middleware.call('service.restart', 'syslogd'))

            # The following should be backgrounded since they may be quite
            # long-running.
            await self.middleware.call('smb.configure', False)

        return await self.config()

    async def _query_pool_for_system_dataset(self, exclude_pool):
        for name in await self._query_pools_names_for_system_dataset(exclude_pool):
            return await self.middleware.call('pool.query', [['name', '=', name]], {'get': True})

    async def _query_pools_names_for_system_dataset(self, exclude_pool=None):
        return [
            ds['id']
            for ds in await self.middleware.call(
                'pool.dataset.query',
                [
                    ['OR', [
                        # Pools without encryption
                        ['encrypted', '=', False],
                        # Encrypted pools that are not locked
                        ['locked', '=', False],
                        # Passphrase-encrypted pools (system dataset will be unencrypted in this case)
                        ['key_format.value', '=', 'PASSPHRASE'],
                    ]],
                ],
                {'extra': {'retrieve_children': False}},
            )
            if ds['id'] != exclude_pool
        ]

    async def __setup_datasets(self, pool, uuid):
        """
        Make sure system datasets for `pool` exist and have the right mountpoint property
        """
        boot_pool = await self.middleware.call('boot.pool_name')
        root_dataset_is_passphrase_encrypted = (
            pool != boot_pool and
            (await self.middleware.call('pool.dataset.get_instance', pool))['key_format']['value'] == 'PASSPHRASE'
        )
        datasets = [i[0] for i in self.__get_datasets(pool, uuid)]
        datasets_prop = {
            i['id']: i['properties'] for i in await self.middleware.call('zfs.dataset.query', [('id', 'in', datasets)])
        }
        for dataset in datasets:
            props = {'mountpoint': 'legacy', 'readonly': 'off', 'snapdir': 'hidden'}
            # Disable encryption for pools with passphrase-encrypted root datasets so that system dataset could be
            # automatically mounted on system boot.
            if root_dataset_is_passphrase_encrypted:
                props['encryption'] = 'off'
            is_cores_ds = dataset.endswith('/cores')
            if is_cores_ds:
                props['quota'] = '1G'
            if dataset not in datasets_prop:
                await self.middleware.call('zfs.dataset.create', {
                    'name': dataset,
                    'properties': props,
                })
            elif is_cores_ds and datasets_prop[dataset]['used']['parsed'] >= 1024 ** 3:
                try:
                    await self.middleware.call('zfs.dataset.delete', dataset, {'force': True, 'recursive': True})
                    await self.middleware.call('zfs.dataset.create', {
                        'name': dataset,
                        'properties': props,
                    })
                except Exception:
                    self.logger.warning("Failed to replace dataset [%s].", dataset, exc_info=True)
            else:
                update_props_dict = {k: {'value': v} for k, v in props.items()
                                     if datasets_prop[dataset][k]['value'] != v}
                if update_props_dict:
                    await self.middleware.call(
                        'zfs.dataset.update',
                        dataset,
                        {'properties': update_props_dict},
                    )

    async def __mount(self, pool, uuid, path=SYSDATASET_PATH):
        mounted = False
        for dataset, name in self.__get_datasets(pool, uuid):
            if name:
                mountpoint = f'{path}/{name}'
            else:
                mountpoint = path
            if os.path.ismount(mountpoint):
                continue
            if not os.path.isdir(mountpoint):
                os.mkdir(mountpoint)
            await run('mount', '-t', 'zfs', dataset, mountpoint, check=True)
            mounted = True

        # make sure the glustereventsd webhook dir and
        # config file exist
        init_job = await self.middleware.call('gluster.eventsd.init')
        await init_job.wait()
        if init_job.error:
            self.logger.error(
                'Failed to initialize %s directory with error: %s',
                CTDBConfig.CTDB_VOL_NAME.value,
                init_job.error
            )

        return mounted

    async def __umount(self, pool, uuid):
        await run('umount', '/var/lib/systemd/coredump', check=False)

        flags = '-f' if not await self.middleware.call('failover.licensed') else '-l'
        for dataset, name in reversed(self.__get_datasets(pool, uuid)):
            try:
                await run('umount', flags, dataset)
            except subprocess.CalledProcessError as e:
                stderr = e.stderr.decode()
                if 'no mount point specified' in stderr:
                    # Already unmounted
                    continue

                error = f'Unable to umount {dataset}: {stderr}'
                if 'target is busy' in stderr:
                    mountpoint = None
                    for partition in psutil.disk_partitions():
                        if partition.device == dataset:
                            mountpoint = partition.mountpoint
                            break

                    if mountpoint is not None:
                        error += f'\nThe following processes are using {mountpoint!r}: ' + json.dumps(
                            await self.middleware.call('pool.dataset.processes_using_paths', [mountpoint], True),
                            indent=2,
                        )

                raise CallError(error) from None

    def __get_datasets(self, pool, uuid):
        return [(f'{pool}/.system', '')] + [
            (f'{pool}/.system/{i}', i) for i in [
                'cores', 'samba4', f'syslog-{uuid}',
                f'rrd-{uuid}', f'configs-{uuid}',
                'webui', 'services',
                'glusterd', CTDBConfig.CTDB_VOL_NAME.value,
            ]
        ]

    @private
    async def migrate(self, _from, _to):

        config = await self.config()

        await self.__setup_datasets(_to, config['uuid'])

        if _from:
            path = '/tmp/system.new'
            if not os.path.exists('/tmp/system.new'):
                os.mkdir('/tmp/system.new')
            else:
                # Make sure we clean up any previous attempts
                await run('umount', '-R', path, check=False)
        else:
            path = SYSDATASET_PATH
        await self.__mount(_to, config['uuid'], path=path)

        async with self._release_system_dataset():
            if _from:
                cp = await run('rsync', '-az', f'{SYSDATASET_PATH}/', '/tmp/system.new', check=False)
                if cp.returncode == 0:
                    # Let's make sure that we don't have coredump directory mounted
                    await run('umount', '/var/lib/systemd/coredump', check=False)
                    await self.__umount(_from, config['uuid'])
                    await self.__umount(_to, config['uuid'])
                    await self.__mount(_to, config['uuid'], SYSDATASET_PATH)
                    proc = await Popen(f'zfs list -H -o name {_from}/.system|xargs zfs destroy -r', shell=True)
                    await proc.communicate()

                    os.rmdir('/tmp/system.new')
                else:
                    raise CallError(f'Failed to rsync from {SYSDATASET_PATH}: {cp.stderr.decode()}')

    @asynccontextmanager
    async def _release_system_dataset(self):
        restart = ['collectd', 'rrdcached', 'syslogd']

        if await self.middleware.call('service.started', 'cifs'):
            restart.insert(0, 'cifs')
        if await self.middleware.call('service.started', 'glusterd'):
            restart.insert(0, 'glusterd')
        if await self.middleware.call('service.started_or_enabled', 'webdav'):
            restart.append('webdav')
        if await self.middleware.call('service.started', 'open-vm-tools'):
            restart.append('open-vm-tools')
        if await self.middleware.call('service.started', 'idmap'):
            restart.append('idmap')
        if await self.middleware.call('service.started', 'nmbd'):
            restart.append('nmbd')

        try:
            await self.middleware.call('cache.put', 'use_syslog_dataset', False)
            await self.middleware.call('service.restart', 'syslogd')

            # Middleware itself will log to syslog dataset.
            # This may be prone to a race condition since we dont wait the workers to stop
            # logging, however all the work before umount seems to make it seamless.
            await self.middleware.call('core.stop_logging')

            for i in restart:
                await self.middleware.call('service.stop', i)

            await self.middleware.call('tdb.close_sysdataset_handles')
            yield
        finally:
            await self.middleware.call('cache.pop', 'use_syslog_dataset')

            restart.reverse()
            for i in restart:
                await self.middleware.call('service.start', i)


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
    middleware.register_hook('pool.post_create', pool_post_create)
    # Reconfigure system dataset first thing after we import a pool.
    middleware.register_hook('pool.post_import', pool_post_import, order=-10000)
    middleware.register_hook('pool.pre_export', pool_pre_export, order=40, raise_error=True)

    try:
        if not os.path.exists('/var/cache/nscd') or not os.path.islink('/var/cache/nscd'):
            if os.path.exists('/var/cache/nscd'):
                shutil.rmtree('/var/cache/nscd')

            os.makedirs('/tmp/cache/nscd', exist_ok=True)

            if not os.path.islink('/var/cache/nscd'):
                os.symlink('/tmp/cache/nscd', '/var/cache/nscd')
    except Exception:
        middleware.logger.error('Error moving cache away from boot pool', exc_info=True)
