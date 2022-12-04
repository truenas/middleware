import errno
import os

import middlewared.sqlalchemy as sa

from middlewared.plugins.boot import BOOT_POOL_NAME_VALID
from middlewared.plugins.zfs_.validation_utils import validate_pool_name
from middlewared.schema import Bool, Dict, Int, List, Patch, Ref, Str
from middlewared.service import accepts, CallError, CRUDService, job, private, returns, ValidationErrors
from middlewared.service_exception import InstanceNotFound
from middlewared.validators import Range

from .utils import ZFS_CHECKSUM_CHOICES, ZFS_ENCRYPTION_ALGORITHM_CHOICES, ZPOOL_CACHE_FILE


class PoolModel(sa.Model):
    __tablename__ = 'storage_volume'

    id = sa.Column(sa.Integer(), primary_key=True)
    vol_name = sa.Column(sa.String(120), unique=True)
    vol_guid = sa.Column(sa.String(50))
    vol_encrypt = sa.Column(sa.Integer(), default=0)
    vol_encryptkey = sa.Column(sa.String(50))


class EncryptedDiskModel(sa.Model):
    __tablename__ = 'storage_encrypteddisk'

    id = sa.Column(sa.Integer(), primary_key=True)
    encrypted_volume_id = sa.Column(sa.ForeignKey('storage_volume.id', ondelete='CASCADE'))
    encrypted_disk_id = sa.Column(sa.ForeignKey('storage_disk.disk_identifier', ondelete='SET NULL'), nullable=True)
    encrypted_provider = sa.Column(sa.String(120), unique=True)


class PoolService(CRUDService):

    ENTRY = Dict(
        'pool_entry',
        Int('id', required=True),
        Str('name', required=True),
        Str('guid', required=True),
        Int('encrypt', required=True),
        Str('encryptkey', required=True),
        Str('encryptkey_path', null=True, required=True),
        Bool('is_decrypted', required=True),
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
        Bool('is_upgraded'),
        Bool('healthy', required=True),
        Bool('warning', required=True),
        Str('status_detail', required=True, null=True),
        Int('size', required=True, null=True),
        Int('allocated', required=True, null=True),
        Int('free', required=True, null=True),
        Int('freeing', required=True, null=True),
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

    @accepts(Str('name'))
    @returns(Ref('pool_entry'))
    async def get_instance_by_name(self, name):
        """
        Returns pool with name `name`. If `name` is not found, Validation error is raised.
        """
        pool = await self.query([['name', '=', name]])
        if not pool:
            raise InstanceNotFound(f'Pool {name} does not exist')

        return pool[0]

    @private
    @accepts(Str('pool_name'))
    @returns(Ref('pool_entry'))
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
            'topology': None,
            'healthy': False,
            'warning': False,
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
            'autotrim': {
                'parsed': 'off',
                'rawvalue': 'off',
                'source': 'DEFAULT',
                'value': 'off'
            },
            'encryptkey_path': None,
            'is_decrypted': True,
        }

        if info := await self.middleware.call('zfs.pool.query', [('name', '=', pool_name)]):
            info = info[0]
            rv.update({
                'status': info['status'],
                'scan': info['scan'],
                'topology': await self.middleware.call('pool.transform_topology', info['groups']),
                'healthy': info['healthy'],
                'warning': info['warning'],
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
            })

        return rv

    @private
    def pool_extend_context(self, rows, extra):
        return {
            "extra": extra,
        }

    @private
    def pool_extend(self, pool, context):

        """
        If pool is encrypted we need to check if the pool is imported
        or if all geli providers exist.
        """
        if context['extra'].get('is_upgraded'):
            pool['is_upgraded'] = self.middleware.call_sync('pool.is_upgraded_by_name', pool['name'])

        # WebUI expects the same data as in `boot.get_state`
        pool |= self.middleware.call_sync('pool.pool_normalize_info', pool['name'])
        return pool

    async def __convert_topology_to_vdevs(self, topology):
        # We do two things here:
        # 1. Gather all disks transversing the topology
        # 2. Keep track of the vdev each disk is supposed to be located
        #    along with a flag whether we should use swap partition in said vdev
        # This is required so we can format all disks in one pass, allowing it
        # to be performed in parallel if we wish to do so.
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
                vdevs.append(vdev)
                # cache and log devices should not have a swap
                create_swap = True if i == 'data' else False
                for disk in t_vdev['disks']:
                    disks[disk] = {'vdev': vdev_devs_list, 'create_swap': create_swap}

        if topology.get('spares'):
            vdev_devs_list = []
            vdevs.append({
                'root': 'SPARE',
                'type': 'STRIPE',
                'devices': vdev_devs_list,
            })
            for disk in topology['spares']:
                disks[disk] = {'vdev': vdev_devs_list, 'create_swap': True}

        return disks, vdevs

    @private
    async def restart_services(self):
        await self.middleware.call('service.reload', 'disk')
        # regenerate crontab because of scrub
        await self.middleware.call('service.restart', 'cron')

    async def __common_validation(self, verrors, data, schema_name, old=None):

        if 'topology' not in data:
            return

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
                    rv.append({
                        'type': i['type'],
                        'disks': [j['type'] for j in i['children']],
                    })
            return rv

        for topology_type in ('data', 'special', 'dedup'):
            lastdatatype = None
            topology_data = list(data['topology'].get(topology_type) or [])
            if old:
                topology_data += disk_to_stripe(topology_type)
            for i, vdev in enumerate(topology_data):
                numdisks = len(vdev['disks'])
                minmap = {
                    'STRIPE': 1,
                    'MIRROR': 2,
                    'RAIDZ1': 3,
                    'RAIDZ2': 4,
                    'RAIDZ3': 5,
                }
                mindisks = minmap[vdev['type']]
                if numdisks < mindisks:
                    verrors.add(
                        f'{schema_name}.topology.{topology_type}.{i}.disks',
                        f'You need at least {mindisks} disk(s) for this vdev type.',
                    )

                if lastdatatype and lastdatatype != vdev['type']:
                    verrors.add(
                        f'{schema_name}.topology.{topology_type}.{i}.type',
                        f'You are not allowed to create a pool with different {topology_type} vdev types '
                        f'({lastdatatype} and {vdev["type"]}).',
                    )
                lastdatatype = vdev['type']

        for i in ('cache', 'log', 'spare'):
            value = data['topology'].get(i)
            if value and len(value) > 1:
                verrors.add(
                    f'{schema_name}.topology.{i}',
                    f'Only one row for the virtual device of type {i} is allowed.',
                )

    @accepts(Dict(
        'pool_create',
        Str('name', max_length=50, required=True),
        Bool('encryption', default=False),
        Str('deduplication', enum=[None, 'ON', 'VERIFY', 'OFF'], default=None, null=True),
        Str('checksum', enum=[None] + ZFS_CHECKSUM_CHOICES, default=None, null=True),
        Dict(
            'encryption_options',
            Bool('generate_key', default=False),
            Int('pbkdf2iters', default=350000, validators=[Range(min=100000)]),
            Str('algorithm', default='AES-256-GCM', enum=ZFS_ENCRYPTION_ALGORITHM_CHOICES),
            Str('passphrase', default=None, null=True, validators=[Range(min=8)], empty=False, private=True),
            Str('key', default=None, null=True, validators=[Range(min=64, max=64)], private=True),
            register=True
        ),
        Dict(
            'topology',
            List('data', items=[
                Dict(
                    'datavdevs',
                    Str('type', enum=['RAIDZ1', 'RAIDZ2', 'RAIDZ3', 'MIRROR', 'STRIPE'], required=True),
                    List('disks', items=[Str('disk')], required=True),
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
    ))
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

        await self.__common_validation(verrors, data, 'pool_create')
        disks, vdevs = await self.__convert_topology_to_vdevs(data['topology'])
        verrors.add_child(
            'pool_create',
            await self.middleware.call('disk.check_disks_availability', list(disks), data['allow_duplicate_serials']),
        )
        verrors.check()

        if osize := (await self.middleware.call('system.advanced.config'))['overprovision']:
            if disks := {disk: osize for disk in sum([vdev['disks'] for vdev in data['topology'].get('log', [])], [])}:
                # will log errors if there are any so it won't crash here (this matches CORE behavior)
                await (await self.middleware.call('disk.resize', disks, True)).wait()

        await self.middleware.call('pool.format_disks', job, disks)

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
            'mountpoint': f'/{data["name"]}',
            **encryption_dict
        }

        dedup = data.get('deduplication')
        if dedup:
            fsoptions['dedup'] = dedup.lower()

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
        self.middleware.create_task(self.middleware.call('disk.swaps_configure'))
        self.middleware.create_task(self.middleware.call('pool.restart_services'))

        pool = await self.get_instance(pool_id)
        await self.middleware.call_hook('pool.post_create', pool=pool)
        await self.middleware.call_hook('pool.post_create_or_update', pool=pool)
        await self.middleware.call_hook(
            'dataset.post_create', {'encrypted': bool(encryption_dict), **encrypted_dataset_data}
        )
        self.middleware.send_event('pool.query', 'ADDED', id=pool_id, fields=pool)
        return pool

    @accepts(Int('id'), Patch(
        'pool_create', 'pool_update',
        ('add', {'name': 'autotrim', 'type': 'str', 'enum': ['ON', 'OFF']}),
        ('rm', {'name': 'name'}),
        ('rm', {'name': 'encryption'}),
        ('rm', {'name': 'encryption_options'}),
        ('rm', {'name': 'deduplication'}),
        ('rm', {'name': 'checksum'}),
        ('edit', {'name': 'topology', 'method': lambda x: setattr(x, 'update', True)}),
    ))
    @job(lock='pool_createupdate')
    async def do_update(self, job, id, data):
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
        pool = await self.get_instance(id)

        verrors = ValidationErrors()

        await self.__common_validation(verrors, data, 'pool_update', old=pool)
        disks = vdevs = None
        if 'topology' in data:
            disks, vdevs = await self.__convert_topology_to_vdevs(data['topology'])
            verrors.add_child(
                'pool_update',
                await self.middleware.call(
                    'disk.check_disks_availability', list(disks), data['allow_duplicate_serials']
                )
            )
        verrors.check()

        if disks and vdevs:
            await self.middleware.call('pool.format_disks', job, disks)

            job.set_progress(90, 'Extending ZFS Pool')
            extend_job = await self.middleware.call('zfs.pool.extend', pool['name'], vdevs)
            await extend_job.wait()

            if extend_job.error:
                raise CallError(extend_job.error)

        if 'autotrim' in data:
            await self.middleware.call('zfs.pool.update', pool['name'], {'properties': {
                'autotrim': {'value': data['autotrim'].lower()},
            }})

        pool = await self.get_instance(id)
        await self.middleware.call_hook('pool.post_create_or_update', pool=pool)
        return pool
