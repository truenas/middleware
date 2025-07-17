import errno
import os

import middlewared.sqlalchemy as sa

from fenced.fence import ExitCode as FencedExitCodes

from middlewared.plugins.boot import BOOT_POOL_NAME_VALID
from middlewared.plugins.zfs_.validation_utils import validate_pool_name
from middlewared.schema import Bool, Dict, Int, List, Patch, Str
from middlewared.service import accepts, CallError, CRUDService, job, private, returns, ValidationErrors
from middlewared.utils.size import format_size
from middlewared.validators import Match, Range

from .utils import (
    ZFS_CHECKSUM_CHOICES, ZFS_ENCRYPTION_ALGORITHM_CHOICES, ZPOOL_CACHE_FILE, RE_DRAID_DATA_DISKS, RE_DRAID_SPARE_DISKS
)


class PoolModel(sa.Model):
    __tablename__ = 'storage_volume'

    id = sa.Column(sa.Integer(), primary_key=True)
    vol_name = sa.Column(sa.String(120), unique=True)
    vol_guid = sa.Column(sa.String(50))


class PoolService(CRUDService):

    ENTRY = Dict(
        'pool_entry',
        Int('id', required=True),
        Str('name', required=True),
        Str('guid', required=True),
        Str('status', required=True),
        Str('path', required=True),
        Dict(
            'scan',
            additional_attrs=True,
            required=True,
            null=True,
            example={
                'function': None,
                'state': None,
                'start_time': None,
                'end_time': None,
                'percentage': None,
                'bytes_to_process': None,
                'bytes_processed': None,
                'bytes_issued': None,
                'pause': None,
                'errors': None,
                'total_secs_left': None,
            }
        ),
        Dict(
            'expand',
            additional_attrs=True,
            required=True,
            null=True,
            example={
                'state': 'FINISHED',
                'expanding_vdev': 0,
                'start_time': None,
                'end_time': None,
                'bytes_to_reflow': 835584,
                'bytes_reflowed': 978944,
                'waiting_for_resilver': 0,
                'total_secs_left': None,
                'percentage': 85.35564853556485,
            },
        ),
        Bool('is_upgraded'),
        Bool('healthy', required=True),
        Bool('warning', required=True),
        Str('status_code', required=True, null=True),
        Str('status_detail', required=True, null=True),
        Int('size', required=True, null=True),
        Int('allocated', required=True, null=True),
        Int('free', required=True, null=True),
        Int('freeing', required=True, null=True),
        Int('dedup_table_size', required=True, null=True),
        Str('dedup_table_quota', required=True, null=True),
        Str('fragmentation', required=True, null=True),
        Str('size_str', required=True, null=True),
        Str('allocated_str', required=True, null=True),
        Str('free_str', required=True, null=True),
        Str('freeing_str', required=True, null=True),
        Dict(
            'autotrim',
            required=True,
            additional_attrs=True,
            example={
                'parsed': 'off',
                'rawvalue': 'off',
                'source': 'DEFAULT',
                'value': 'off',
            }
        ),
        Dict(
            'topology',
            List('data', required=True),
            List('log', required=True),
            List('cache', required=True),
            List('spare', required=True),
            List('special', required=True),
            List('dedup', required=True),
            required=True,
            null=True,
        )
    )

    class Config:
        datastore = 'storage.volume'
        datastore_extend = 'pool.pool_extend'
        datastore_extend_context = 'pool.pool_extend_context'
        datastore_prefix = 'vol_'
        event_send = False
        cli_namespace = 'storage.pool'
        role_prefix = 'POOL'

    @private
    @accepts(Str('pool_name'))
    @returns(Patch('pool_entry', 'pool_normalize', ('rm', {'name': 'id'}), ('rm', {'name': 'guid'})))
    async def pool_normalize_info(self, pool_name):
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

            rv.update({
                'status': status,
                'scan': info['scan'],
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

        return rv

    @private
    def pool_extend_context(self, rows, extra):
        return {
            "extra": extra,
        }

    @private
    def pool_extend(self, pool, context):
        if context['extra'].get('is_upgraded'):
            pool['is_upgraded'] = self.middleware.call_sync('pool.is_upgraded_by_name', pool['name'])

        # WebUI expects the same data as in `boot.get_state`
        pool |= self.middleware.call_sync('pool.pool_normalize_info', pool['name'])
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
        await self.middleware.call('service.restart', 'cron')

    async def _process_topology(self, schema_name, data, old=None):
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
                                       data['allow_duplicate_serials']),
        )
        verrors.check()

        disks_cache = dict(map(lambda x: (x['devname'], x), await self.middleware.call('disk.query')))
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
                    vdev.update({
                        'draid_data_disks': vdev.get('draid_data_disks'),
                        'draid_spare_disks': vdev.get('draid_spare_disks', 0),
                    })
                    nparity = int(vdev['type'][-1:])
                    verrors.extend(await self.middleware.call(
                        'zfs.pool.validate_draid_configuration', f'{topology_type}.{i}', numdisks, nparity, vdev
                    ))

                    if data['topology'].get('spare'):
                        verrors.add(
                            'topology.spare',
                            'Dedicated spare disks should not be used with dRAID.'
                        )
                else:
                    for k in ('draid_data_disks', 'draid_spare_disks'):
                        if k in vdev:
                            verrors.add(
                                f'topology.{topology_type}.{i}.{k}',
                                'This property is only valid with dRAID vdevs.',
                            )

                if lastdatatype and lastdatatype != vdev['type']:
                    verrors.add(
                        f'topology.{topology_type}.{i}.type',
                        f'You are not allowed to create a pool with different {topology_type} vdev types '
                        f'({lastdatatype} and {vdev["type"]}).',
                    )
                lastdatatype = vdev['type']

        for i in ('cache', 'log', 'spare'):
            value = data['topology'].get(i)
            if value and len(value) > 1:
                verrors.add(
                    f'topology.{i}',
                    f'Only one row for the virtual device of type {i} is allowed.',
                )

        return verrors

    @accepts(Dict(
        'pool_create',
        Str(
            'name',
            max_length=50,
            validators=[Match(r'^\S+$', explanation='Pool name must not contain whitespace')],
            required=True
        ),
        Bool('encryption', default=False),
        Str('dedup_table_quota', default='AUTO', enum=['AUTO', None, 'CUSTOM'], null=True),
        Int('dedup_table_quota_value', null=True, default=None, validators=[Range(min_=1)]),
        Str('deduplication', enum=[None, 'ON', 'VERIFY', 'OFF'], default=None, null=True),
        Str('checksum', enum=[None] + ZFS_CHECKSUM_CHOICES, default=None, null=True),
        Dict(
            'encryption_options',
            Bool('generate_key', default=False),
            Int('pbkdf2iters', default=350000, validators=[Range(min_=100000)]),
            Str('algorithm', default='AES-256-GCM', enum=ZFS_ENCRYPTION_ALGORITHM_CHOICES),
            Str('passphrase', default=None, null=True, validators=[Range(min_=8)], empty=False, private=True),
            Str('key', default=None, null=True, validators=[Range(min_=64, max_=64)], private=True),
            register=True
        ),
        Dict(
            'topology',
            List('data', items=[
                Dict(
                    'datavdevs',
                    Str('type', enum=[
                        'DRAID1', 'DRAID2', 'DRAID3', 'RAIDZ1', 'RAIDZ2', 'RAIDZ3', 'MIRROR', 'STRIPE'
                    ], required=True),
                    List('disks', items=[Str('disk')], required=True),
                    Int('draid_data_disks'),
                    Int('draid_spare_disks'),
                ),
            ], required=True),
            List('special', items=[
                Dict(
                    'specialvdevs',
                    Str('type', enum=['MIRROR', 'STRIPE'], required=True),
                    List('disks', items=[Str('disk')], required=True),
                ),
            ]),
            List('dedup', items=[
                Dict(
                    'dedupvdevs',
                    Str('type', enum=['MIRROR', 'STRIPE'], required=True),
                    List('disks', items=[Str('disk')], required=True),
                ),
            ]),
            List('cache', items=[
                Dict(
                    'cachevdevs',
                    Str('type', enum=['STRIPE'], required=True),
                    List('disks', items=[Str('disk')], required=True),
                ),
            ]),
            List('log', items=[
                Dict(
                    'logvdevs',
                    Str('type', enum=['STRIPE', 'MIRROR'], required=True),
                    List('disks', items=[Str('disk')], required=True),
                ),
            ]),
            List('spares', items=[Str('disk')]),
            required=True,
        ),
        Bool('allow_duplicate_serials', default=False),
        register=True,
    ), audit='Pool create', audit_extended=lambda data: data['name'])
    @job(lock='pool_createupdate')
    async def do_create(self, job, data):
        """
        Create a new ZFS Pool.

        `topology` is a object which requires at least one `data` entry.
        All of `data` entries (vdevs) require to be of the same type.

        `deduplication` when set to ON or VERIFY makes sure that no block of data is duplicated in the pool. When
        VERIFY is specified, if two blocks have similar signatures, byte to byte comparison is performed to ensure that
        the blocks are identical. This should be used in special circumstances as it carries a significant overhead.

        `encryption` when enabled will create an ZFS encrypted root dataset for `name` pool.

        `encryption_options` specifies configuration for encryption of root dataset for `name` pool.
        `encryption_options.passphrase` must be specified if encryption for root dataset is desired with a passphrase
        as a key.
        Otherwise a hex encoded key can be specified by providing `encryption_options.key`.
        `encryption_options.generate_key` when enabled automatically generates the key to be used
        for dataset encryption.

        It should be noted that keys are stored by the system for automatic locking/unlocking
        on import/export of encrypted datasets. If that is not desired, dataset should be created
        with a passphrase as a key.

        Example of `topology`:

            {
                "data": [
                    {"type": "RAIDZ1", "disks": ["da1", "da2", "da3"]}
                ],
                "cache": [
                    {"type": "STRIPE", "disks": ["da4"]}
                ],
                "log": [
                    {"type": "STRIPE", "disks": ["da5"]}
                ],
                "spares": ["da6"]
            }


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

        if not data['topology']['data']:
            verrors.add('pool_create.topology.data', 'At least one data vdev is required')

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

        disks, vdevs = await self._process_topology('pool_create', data)

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

        if any(topology['type'].startswith('DRAID') for topology in data['topology']['data']):
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
            await self.middleware.call('zfs.dataset.update', data['name'], {
                'properties': {
                    'mountpoint': {'source': 'INHERIT'},
                },
            })
            await self.middleware.call('zfs.dataset.mount', data['name'])

            pool = {
                'name': data['name'],
                'guid': z_pool['guid'],
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

    @accepts(Int('id'), Patch(
        'pool_create', 'pool_update',
        ('add', {'name': 'autotrim', 'type': 'str', 'enum': ['ON', 'OFF']}),
        ('rm', {'name': 'name'}),
        ('rm', {'name': 'encryption'}),
        ('rm', {'name': 'encryption_options'}),
        ('rm', {'name': 'deduplication'}),
        ('rm', {'name': 'checksum'}),
        ('edit', {'name': 'topology', 'method': lambda x: setattr(x, 'update', True)}),
    ), audit='Pool update', audit_callback=True)
    @job(lock='pool_createupdate')
    async def do_update(self, job, audit_callback, id_, data):
        """
        Update pool of `id`, adding the new topology.

        The `type` of `data` must be the same of existing vdevs.

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

        disks = vdevs = None
        if 'topology' in data:
            disks, vdevs = await self._process_topology('pool_update', data, pool)

        verrors = ValidationErrors()
        dedup_table_quota_value = await self.validate_dedup_table_quota(data, verrors, 'pool_update')
        verrors.check()

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

    @accepts(Str('pool_name'), roles=['POOL_READ'])
    @returns()
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
            if any(group['type'] == 'draid' for group in pool[0]['groups']['data']):
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
