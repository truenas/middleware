import errno
import os

import middlewared.sqlalchemy as sa

from fenced.fence import ExitCode as FencedExitCodes

from middlewared.api import api_method
from middlewared.api.base import BaseModel, Excluded, excluded_field
from middlewared.api.current import (
    PoolEntry, PoolCreateArgs, PoolCreateResult, PoolUpdateArgs,
    PoolUpdateResult, PoolValidateNameArgs, PoolValidateNameResult
)
from middlewared.plugins.pool_.utils import UpdateImplArgs
from middlewared.plugins.zfs_.validation_utils import validate_pool_name
from middlewared.plugins.zfs.mount_unmount_impl import MountArgs
from middlewared.service import CallError, CRUDService, job, private, ValidationErrors
from middlewared.utils import BOOT_POOL_NAME_VALID
from middlewared.utils.sed import SEDStatus
from middlewared.utils.size import format_size

from .utils import ZPOOL_CACHE_FILE, RE_DRAID_DATA_DISKS, RE_DRAID_SPARE_DISKS


class PoolPoolNormalizeInfo(PoolEntry):
    id: Excluded = excluded_field()
    guid: Excluded = excluded_field()


class PoolPoolNormalizeInfoArgs(BaseModel):
    pool_name: str
    sed_cache: dict | None = None
    all_sed_pool: bool = False


class PoolPoolNormalizeInfoResult(BaseModel):
    result: PoolPoolNormalizeInfo


class PoolModel(sa.Model):
    __tablename__ = 'storage_volume'

    id = sa.Column(sa.Integer(), primary_key=True)
    vol_name = sa.Column(sa.String(120), unique=True)
    vol_guid = sa.Column(sa.String(50))
    vol_all_sed = sa.Column(sa.Boolean(), default=False, nullable=True)


class PoolService(CRUDService):

    class Config:
        datastore = 'storage.volume'
        datastore_extend = 'pool.pool_extend'
        datastore_extend_context = 'pool.pool_extend_context'
        datastore_prefix = 'vol_'
        event_send = False
        cli_namespace = 'storage.pool'
        role_prefix = 'POOL'
        entry = PoolEntry

    @api_method(PoolPoolNormalizeInfoArgs, PoolPoolNormalizeInfoResult, private=True)
    async def pool_normalize_info(self, pool_name, sed_cache=None, all_sed_pool=False):
        """
        Returns the current state of 'pool_name' including all vdevs, properties and datasets.

        Common method for `pool.pool_extend` and `boot.get_state` returning a uniform
        data structure for its consumers.
        """
        rv = {
            'name': pool_name,
            'path': '/' if pool_name in BOOT_POOL_NAME_VALID else f'/mnt/{pool_name}',
            'status': 'OFFLINE',
            'scan': None,
            'expand': None,
            'topology': None,
            'healthy': False,
            'warning': False,
            'status_code': None,
            'status_detail': None,
            'size': None,
            'allocated': None,
            'free': None,
            'freeing': None,
            'fragmentation': None,
            'size_str': None,
            'allocated_str': None,
            'free_str': None,
            'freeing_str': None,
            'dedup_table_quota': None,
            'dedup_table_size': None,
            'autotrim': {
                'parsed': 'off',
                'rawvalue': 'off',
                'source': 'DEFAULT',
                'value': 'off'
            },
        }

        if info := await self.middleware.call('zfs.pool.query', [('name', '=', pool_name)]):
            info = info[0]

            # `zpool.c` uses `zpool_get_state_str` to print pool status.
            # This function return value is exposed as `health` property.
            # `SUSPENDED` is the only differing status at the moment.
            status = info['status']
            if info['properties']['health']['value'] == 'SUSPENDED':
                status = 'SUSPENDED'

            # Normalize scan field: if there's no scan data, libzfs returns a dict with None values
            # but the API expects either None or a valid PoolScan object with all required fields
            scan = info['scan']
            if scan and scan['state'] is None:
                scan = None

            rv.update({
                'status': status,
                'scan': scan,
                'expand': info['expand'],
                'topology': await self.middleware.call('pool.transform_topology', info['groups']),
                'healthy': info['healthy'],
                'warning': info['warning'],
                'status_code': info['status_code'],
                'status_detail': info['status_detail'],
                'size': info['properties']['size']['parsed'],
                'allocated': info['properties']['allocated']['parsed'],
                'free': info['properties']['free']['parsed'],
                'freeing': info['properties']['freeing']['parsed'],
                'fragmentation': info['properties']['fragmentation']['parsed'],
                'size_str': info['properties']['size']['rawvalue'],
                'allocated_str': info['properties']['allocated']['rawvalue'],
                'free_str': info['properties']['free']['rawvalue'],
                'freeing_str': info['properties']['freeing']['rawvalue'],
                'autotrim': info['properties']['autotrim'],
                'dedup_table_quota': info['properties']['dedup_table_quota']['parsed'],
                'dedup_table_size': info['properties']['dedup_table_size']['parsed'],
            })
        else:
            # If system is licensed for SED and we have SED disks which are locked, we would like to
            # update status detail attr to say that it is possible because of locked disks, the pool
            # did not import
            sed_cache = {} if sed_cache is None else sed_cache
            # Reason for having this explicit dict cache workflow is so that in pool extend context, we
            # avoid querying SED disks at all and this code path only gets triggered if there is actually
            # a zpool which failed to import and locked SED disks might be to blame
            #
            # We only want to initialize sed cache here if system is licensed for it and the pool in qeustion
            # is actually an all sed based pool
            if all_sed_pool and not sed_cache:
                sed_enabled = await self.middleware.call('system.sed_enabled')
                locked_sed_disks = {disk['name'] for disk in await self.middleware.call('disk.query', [
                    ['sed_status', '=', SEDStatus.LOCKED]
                ], {'extra': {'sed_status': True}})} if sed_enabled else set()
                sed_cache.update({
                    'sed_enabled': sed_enabled,
                    'locked_sed_disks': locked_sed_disks,
                })

            if all_sed_pool and sed_cache['sed_enabled']:
                if sed_cache['locked_sed_disks']:
                    rv['status_code'] = 'LOCKED_SED_DISKS'
                    rv['status_detail'] = ('Pool might have failed to import because of '
                                           f'{", ".join(sed_cache["locked_sed_disks"])!r} SED disk(s) being locked')

        return rv

    @private
    def pool_extend_context(self, rows, extra):
        return {
            "extra": extra,
            "sed_cache": dict(),
        }

    @private
    def pool_extend(self, pool, context):
        if context['extra'].get('is_upgraded'):
            pool['is_upgraded'] = self.middleware.call_sync('pool.is_upgraded_by_name', pool['name'])

        # WebUI expects the same data as in `boot.get_state`
        pool |= self.middleware.call_sync(
            'pool.pool_normalize_info', pool['name'], context['sed_cache'], pool['all_sed'],
        )
        return pool

    async def __convert_topology_to_vdevs(self, topology):
        # Gather all disks transversing the topology so we can
        # format all disks in one pass, allowing it to be performed
        # in parallel if we wish to do so.
        disks = {}
        vdevs = []
        for i in ('data', 'cache', 'log', 'special', 'dedup'):
            t_vdevs = topology.get(i)
            if not t_vdevs:
                continue
            for t_vdev in t_vdevs:
                vdev_devs_list = []
                vdev = {
                    'root': i.upper(),
                    'type': t_vdev['type'],
                    'devices': vdev_devs_list,
                }
                if t_vdev['type'].startswith('DRAID'):
                    vdev['draid_data_disks'] = t_vdev['draid_data_disks']
                    vdev['draid_spare_disks'] = t_vdev['draid_spare_disks']
                vdevs.append(vdev)
                for disk in t_vdev['disks']:
                    disks[disk] = {'vdev': vdev_devs_list}

        if topology.get('spares'):
            vdev_devs_list = []
            vdevs.append({
                'root': 'SPARE',
                'type': 'STRIPE',
                'devices': vdev_devs_list,
            })
            for disk in topology['spares']:
                disks[disk] = {'vdev': vdev_devs_list}

        return disks, vdevs

    @private
    async def restart_services(self):
        # regenerate crontab because of scrub
        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

    async def _process_topology(
        self, schema_name: str, data: dict, old: dict | None = None, validate_all_sed: bool = False
    ):
        verrors = ValidationErrors()

        verrors.add_child(
            schema_name,
            await self._validate_topology(data, old),
        )
        verrors.check()

        disks, vdevs = await self.__convert_topology_to_vdevs(data['topology'])
        verrors.add_child(
            schema_name,
            await self.middleware.call('disk.check_disks_availability', list(disks),
                                       data.get('allow_duplicate_serials', False)),
        )
        verrors.check()

        disks_cache = dict()
        for i in await self.middleware.call('disk.get_disks'):
            disks_cache[i.name] = {'size': i.size_bytes}

        min_data_size = min([
            disks_cache[disk]['size']
            for disk in (
                sum([vdev['disks'] for vdev in data['topology'].get('data', [])], []) +
                (
                    [
                        device['disk']
                        for device in await self.middleware.call(
                            'pool.flatten_topology',
                            {'data': old['topology']['data']},
                        )
                        if device['type'] == 'DISK'
                    ]
                    if old else []
                )
            )
            if disk in disks_cache
        ])
        for spare_disk in data['topology'].get('spares') or []:
            spare_size = disks_cache[spare_disk]['size']
            if spare_size < min_data_size:
                verrors.add(
                    f'{schema_name}.topology',
                    f'Spare {spare_disk} ({format_size(spare_size)}) is smaller than the smallest data disk '
                    f'({format_size(min_data_size)})'
                )
        verrors.check()

        # At this point, we have validated disks and are ready to proceed to the next step in pool creation
        # where we format disks and finally create the pool with necessary configuration
        # We will now try to configure SED disks (if any) automatically
        if validate_all_sed:
            # We will only want to do SED magic on zpool create if consumer has explicitly set that flag
            await self.middleware.call(
                'disk.setup_sed_disks_for_pool', list(disks), f'{schema_name}.topology', validate_all_sed
            )

        return disks, vdevs

    async def _validate_topology(self, data, old=None):
        verrors = ValidationErrors()

        def disk_to_stripe(topology_type):
            """
            We need to convert the original topology to use STRIPE
            instead of DISK to match the user input data
            """
            rv = []
            spare = None
            for i in old['topology'][topology_type]:
                if i['type'] == 'DISK':
                    if spare is None:
                        spare = {
                            'type': 'STRIPE',
                            'disks': [i['path']],
                        }
                        rv.append(spare)
                    else:
                        spare['disks'].append(i['path'])
                else:
                    entry = {
                        'type': i['type'],
                        'disks': [j['type'] for j in i['children']],
                    }
                    if i['type'] == 'DRAID':
                        # This needs to happen because type here says draid only and we need to
                        # normalize it so that it reflects the parity as well i.e DRAID1, DRAID2, etc.
                        # sample value of name here is: draid1:1d:2c:0s-0
                        entry['type'] = f'{i["type"]}{i["name"][len("draid"):len("draid") + 1]}'
                        entry['draid_spare_disks'] = int(RE_DRAID_SPARE_DISKS.findall(i['name'])[0][1:-1])
                        entry['draid_data_disks'] = int(RE_DRAID_DATA_DISKS.findall(i['name'])[0][1:-1])
                    rv.append(entry)
            return rv

        for topology_type in ('data', 'special', 'dedup'):
            lastdatatype = None
            topology_data = list(data['topology'].get(topology_type) or [])
            if old and old['topology']:
                topology_data += disk_to_stripe(topology_type)
            for i, vdev in enumerate(topology_data):
                numdisks = len(vdev['disks'])
                minmap = {
                    'STRIPE': 1,
                    'MIRROR': 2,
                    'DRAID1': 2,
                    'DRAID2': 3,
                    'DRAID3': 4,
                    'RAIDZ1': 3,
                    'RAIDZ2': 4,
                    'RAIDZ3': 5,
                }
                mindisks = minmap[vdev['type']]
                if numdisks < mindisks:
                    verrors.add(
                        f'topology.{topology_type}.{i}.disks',
                        f'You need at least {mindisks} disk(s) for this vdev type.',
                    )

                if vdev['type'].startswith('DRAID'):
                    nparity = int(vdev['type'][-1:])
                    verrors.extend(await self.middleware.call(
                        'zfs.pool.validate_draid_configuration', f'{topology_type}.{i}', numdisks, nparity, vdev
                    ))

                    if data['topology'].get('spares'):
                        verrors.add(
                            'topology.spares',
                            'Dedicated spare disks should not be used with dRAID.'
                        )

                if lastdatatype and lastdatatype != vdev['type']:
                    verrors.add(
                        f'topology.{topology_type}.{i}.type',
                        f'You are not allowed to create a pool with different {topology_type} vdev types '
                        f'({lastdatatype} and {vdev["type"]}).',
                    )
                lastdatatype = vdev['type']

        for i in ('cache', 'log'):
            value = data['topology'].get(i)
            if value and len(value) > 1:
                verrors.add(
                    f'topology.{i}',
                    f'Only one row for the virtual device of type {i} is allowed.',
                )

        return verrors

    @api_method(PoolCreateArgs, PoolCreateResult, audit='Pool create', audit_extended=lambda data: data['name'])
    @job(lock='pool_createupdate')
    async def do_create(self, job, data):
        """
        Create a new ZFS Pool.

        .. examples(websocket)::

          Create a pool named "tank", raidz1 with 3 disks, 1 cache disk, 1 ZIL/log disk
          and 1 hot spare disk.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.create",
                "params": [{
                    "name": "tank",
                    "topology": {
                        "data": [
                            {"type": "RAIDZ1", "disks": ["da1", "da2", "da3"]}
                        ],
                        "cache": [
                            {"type": "STRIPE", "disks": ["da4"]}
                        ],
                        "log": [
                            {"type": "RAIDZ1", "disks": ["da5"]}
                        ],
                        "spares": ["da6"]
                    }
                }]
            }
        """

        verrors = ValidationErrors()

        if await self.middleware.call('pool.query', [('name', '=', data['name'])]):
            verrors.add('pool_create.name', 'A pool with this name already exists.', errno.EEXIST)
        elif not validate_pool_name(data['name']):
            verrors.add('pool_create.name', 'Invalid pool name', errno.EINVAL)

        encryption_dict = await self.middleware.call(
            'pool.dataset.validate_encryption_data', None, verrors, {
                'enabled': data.pop('encryption'), **data.pop('encryption_options'), 'key_file': False,
            }, 'pool_create.encryption_options',
        )

        dedup_table_quota_value = None
        if data['deduplication'] == 'ON':
            dedup_table_quota_value = await self.validate_dedup_table_quota(data, verrors)

        verrors.check()

        is_ha = await self.middleware.call('failover.licensed')
        if is_ha and (rc := await self.middleware.call('failover.fenced.start')):
            if rc == FencedExitCodes.ALREADY_RUNNING.value[0]:
                try:
                    await self.middleware.call('failover.fenced.signal', {'reload': True})
                except Exception:
                    self.logger.error('Unhandled exception reloading fenced', exc_info=True)
            else:
                err = 'Unexpected error starting fenced'
                for i in filter(lambda x: x.value[0] == rc, FencedExitCodes):
                    err = i.value[1]
                raise CallError(err)

        disks, vdevs = await self._process_topology('pool_create', data, None, data['all_sed'])

        if osize := (await self.middleware.call('system.advanced.config'))['overprovision']:
            if log_disks := {disk: osize
                             for disk in sum([vdev['disks'] for vdev in data['topology'].get('log', [])], [])}:
                # will log errors if there are any so it won't crash here (this matches CORE behavior)
                await (await self.middleware.call('disk.resize', log_disks, True)).wait()

        await self.middleware.call('pool.format_disks', job, disks, 0, 30)

        options = {
            'feature@lz4_compress': 'enabled',
            'altroot': '/mnt',
            'cachefile': ZPOOL_CACHE_FILE,
            'failmode': 'continue',
            'autoexpand': 'on',
            'ashift': 12,
        }

        fsoptions = {
            'atime': 'off',
            'aclmode': 'discard',
            'acltype': 'posix',
            'compression': 'lz4',
            'aclinherit': 'passthrough',
            'xattr': 'sa',
            'mountpoint': f'/{data["name"]}',
            **encryption_dict
        }

        if any(
            topology['type'].startswith('DRAID')
            for topology in data['topology']['data'] + data['topology'].get('special', [])
        ):
            fsoptions['recordsize'] = '1M'

        dedup = data.get('deduplication')
        if dedup:
            fsoptions['dedup'] = dedup.lower()
        if dedup_table_quota_value is not None:
            options['dedup_table_quota'] = dedup_table_quota_value

        if data['checksum'] is not None:
            fsoptions['checksum'] = data['checksum'].lower()

        cachefile_dir = os.path.dirname(ZPOOL_CACHE_FILE)
        if not os.path.isdir(cachefile_dir):
            os.makedirs(cachefile_dir)

        pool_id = z_pool = encrypted_dataset_pk = None
        try:
            job.set_progress(90, 'Creating ZFS Pool')

            z_pool = await self.middleware.call('zfs.pool.create', {
                'name': data['name'],
                'vdevs': vdevs,
                'options': options,
                'fsoptions': fsoptions,
            })

            job.set_progress(95, 'Setting pool options')

            # Inherit mountpoint after create because we set mountpoint on creation
            # making it a "local" source.
            await self.middleware.call(
                'pool.dataset.update_impl',
                UpdateImplArgs(name=data['name'], iprops={'mountpoint'})
            )
            await self.middleware.call('zfs.resource.mount', MountArgs(filesystem=data['name']))

            pool = {
                'name': data['name'],
                'guid': z_pool['guid'],
                'all_sed': data['all_sed'],
            }
            pool_id = await self.middleware.call(
                'datastore.insert',
                'storage.volume',
                pool,
                {'prefix': 'vol_'},
            )

            encrypted_dataset_data = {
                'name': data['name'], 'encryption_key': encryption_dict.get('key'),
                'key_format': encryption_dict.get('keyformat')
            }
            encrypted_dataset_pk = await self.middleware.call(
                'pool.dataset.insert_or_update_encrypted_record', encrypted_dataset_data
            )
            await self.middleware.call('datastore.insert', 'storage.scrub', {'volume': pool_id}, {'prefix': 'scrub_'})
        except Exception as e:
            # Something wrong happened, we need to rollback and destroy pool.
            self.logger.debug('Pool %s failed to create with topology %s', data['name'], data['topology'])
            if z_pool:
                try:
                    await self.middleware.call('zfs.pool.delete', data['name'])
                except Exception:
                    self.logger.warning('Failed to delete pool on pool.create rollback', exc_info=True)
            if pool_id:
                await self.middleware.call('datastore.delete', 'storage.volume', pool_id)
            if encrypted_dataset_pk:
                await self.middleware.call(
                    'pool.dataset.delete_encrypted_datasets_from_db', [['id', '=', encrypted_dataset_pk]]
                )
            raise e

        # There is really no point in waiting all these services to reload so do them
        # in background.
        self.middleware.create_task(self.middleware.call('pool.restart_services'))

        pool = await self.get_instance(pool_id)
        await self.middleware.call_hook('pool.post_create', pool=pool)
        await self.middleware.call_hook('pool.post_create_or_update', pool=pool)
        await self.middleware.call_hook(
            'dataset.post_create', {'encrypted': bool(encryption_dict), **encrypted_dataset_data}
        )
        self.middleware.send_event('pool.query', 'ADDED', id=pool_id, fields=pool)
        return pool

    @private
    async def validate_dedup_table_quota(self, data, verrors, schema='pool_create'):
        dedup_table_quota = data.get('dedup_table_quota')
        dedup_table_quota_value = data.get('dedup_table_quota_value')
        if dedup_table_quota != 'CUSTOM' and dedup_table_quota_value is not None:
            verrors.add(
                f'{schema}.dedup_table_quota',
                'You must set Deduplication Table Quota to CUSTOM to specify a value.',
            )
        elif dedup_table_quota == 'CUSTOM' and dedup_table_quota_value is None:
            verrors.add(
                f'{schema}.dedup_table_quota_value',
                'This field is required when Deduplication Table Quota is set to CUSTOM.',
            )

        if verrors or 'dedup_table_quota' not in data:
            return

        if dedup_table_quota is None:
            return 'none'
        elif dedup_table_quota == 'CUSTOM':
            return str(dedup_table_quota_value)
        else:
            return dedup_table_quota.lower()

    @api_method(PoolUpdateArgs, PoolUpdateResult, audit='Pool update', audit_callback=True)
    @job(lock='pool_createupdate')
    async def do_update(self, job, audit_callback, id_, data):
        """
        Update pool of `id`, adding the new topology.

        .. examples(websocket)::

          Add a new set of raidz1 to pool of id 1.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.update",
                "params": [1, {
                    "topology": {
                        "data": [
                            {"type": "RAIDZ1", "disks": ["da7", "da8", "da9"]}
                        ]
                    }
                }]
            }
        """
        pool = await self.get_instance(id_)
        audit_callback(pool['name'])

        verrors = ValidationErrors()
        dedup_table_quota_value = await self.validate_dedup_table_quota(data, verrors, 'pool_update')
        verrors.check()

        disks = vdevs = None
        if 'topology' in data:
            disks, vdevs = await self._process_topology('pool_update', data, pool, pool['all_sed'])

        if disks and vdevs:
            await self.middleware.call('pool.format_disks', job, disks, 0, 80)

            job.set_progress(90, 'Extending ZFS Pool')
            extend_job = await self.middleware.call('zfs.pool.extend', pool['name'], vdevs)
            await extend_job.wait()

            if extend_job.error:
                raise CallError(extend_job.error)

        properties = {}
        if 'autotrim' in data:
            properties['autotrim'] = {'value': data['autotrim'].lower()}

        if dedup_table_quota_value is not None:
            properties['dedup_table_quota'] = {'value': dedup_table_quota_value}

        if (
            zfs_pool := await self.middleware.call('zfs.pool.query', [['name', '=', pool['name']]])
        ) and zfs_pool[0]['properties']['ashift']['source'] == 'DEFAULT':
            # https://ixsystems.atlassian.net/browse/NAS-112093
            properties['ashift'] = {'value': '12'}

        if properties:
            await self.middleware.call('zfs.pool.update', pool['name'], {'properties': properties})

        pool = await self.get_instance(id_)
        await self.middleware.call_hook('pool.post_create_or_update', pool=pool)
        return pool

    @api_method(PoolValidateNameArgs, PoolValidateNameResult, roles=['POOL_READ'])
    def validate_name(self, pool_name):
        """
        Validates `pool_name` is a valid name for a pool.
        """
        verrors = ValidationErrors()
        if not validate_pool_name(pool_name):
            verrors.add(
                'pool_name',
                'Invalid pool name (please refer to https://openzfs.github.io/openzfs-docs/'
                'man/8/zpool-create.8.html#DESCRIPTION for valid rules for pool name)',
                errno.EINVAL
            )
        verrors.check()

        return True

    @private
    async def is_draid_pool(self, pool_name):
        if pool := await self.middleware.call('zfs.pool.query', [['name', '=', pool_name]]):
            if any(
                group['type'] == 'draid'
                for group in pool[0]['groups']['data'] + pool[0]['groups'].get('special', [])
            ):
                return True

        return False


async def retaste_disks_on_standby_hook(middleware, *args, **kwargs):
    if not await middleware.call('failover.licensed'):
        return

    try:
        await middleware.call('failover.call_remote', 'disk.retaste', [], {'raise_connect_error': False})
    except Exception:
        middleware.logger.warning('Failed to retaste disks on standby controller', exc_info=True)


async def setup(middleware):
    middleware.register_hook('pool.post_create_or_update', retaste_disks_on_standby_hook)
