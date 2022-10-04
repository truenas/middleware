import asyncio
from collections import deque
import contextlib
import copy
import enum
import errno
import itertools
import json
import logging
from datetime import datetime, time, timedelta
from pathlib import Path
import os
import re
import secrets
import shutil
import uuid

from collections import defaultdict
from io import BytesIO

from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass
from middlewared.plugins.boot import BOOT_POOL_NAME_VALID
from middlewared.plugins.zfs import ZFSSetPropertyError
from middlewared.plugins.zfs_.validation_utils import validate_dataset_name, validate_pool_name
from middlewared.schema import (
    accepts, Attribute, Bool, Cron,
    Dict, EnumMixin, Int, List,
    Patch, Str, UnixPerm, Any,
    Ref, returns, OROperator, NOT_PROVIDED,
)
from middlewared.service import (
    ConfigService, filterable, item_method, job, pass_app, private, CallError, CRUDService, ValidationErrors, periodic
)
from middlewared.service_exception import InstanceNotFound, ValidationError
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list, run
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.utils.path import is_child
from middlewared.utils.size import MB
from middlewared.validators import Exact, Match, Or, Range, Time

logger = logging.getLogger(__name__)

GELI_KEYPATH = '/data/geli'

RE_HISTORY_ZPOOL_SCRUB = re.compile(r'^([0-9\.\:\-]{19})\s+zpool scrub', re.MULTILINE)
RE_HISTORY_ZPOOL_CREATE = re.compile(r'^([0-9\.\:\-]{19})\s+zpool create', re.MULTILINE)
ZFS_CHECKSUM_CHOICES = [
    'ON', 'OFF', 'FLETCHER2', 'FLETCHER4', 'SHA256', 'SHA512', 'SKEIN', 'EDONR',
]
ZFS_ENCRYPTION_ALGORITHM_CHOICES = [
    'AES-128-CCM', 'AES-192-CCM', 'AES-256-CCM', 'AES-128-GCM', 'AES-192-GCM', 'AES-256-GCM'
]
ZFS_COMPRESSION_ALGORITHM_CHOICES = [
    'OFF', 'LZ4', 'GZIP', 'GZIP-1', 'GZIP-9', 'ZSTD', 'ZSTD-FAST', 'ZLE', 'LZJB',
] + [f'ZSTD-{i}' for i in range(1, 20)] + [
    f'ZSTD-FAST-{i}' for i in itertools.chain(range(1, 11), range(20, 110, 10), range(500, 1500, 500))
]
ZPOOL_CACHE_FILE = '/data/zfs/zpool.cache'
ZPOOL_KILLCACHE = '/data/zfs/killcache'
ZFS_MAX_DATASET_NAME_LEN = 200  # It's really 256, but we should leave some space for snapshot names


class ZfsDeadmanAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Device Is Causing Slow I/O on Pool"
    text = "Device %(vdev)s is causing slow I/O on pool %(pool)s."

    expires_after = timedelta(hours=4)

    hardware = True


class ZFSKeyFormat(enum.Enum):
    HEX = 'HEX'
    PASSPHRASE = 'PASSPHRASE'
    RAW = 'RAW'


class Inheritable(EnumMixin, Attribute):
    def __init__(self, schema, **kwargs):
        self.schema = schema
        if not self.schema.has_default and 'default' not in kwargs and kwargs.pop('has_default', True):
            kwargs['default'] = 'INHERIT'
        super(Inheritable, self).__init__(self.schema.name, **kwargs)

    def clean(self, value):
        if value == 'INHERIT':
            return value
        elif value is NOT_PROVIDED and self.has_default:
            return copy.deepcopy(self.default)

        return self.schema.clean(value)

    def validate(self, value):
        if value == 'INHERIT':
            return

        return self.schema.validate(value)

    def to_json_schema(self, parent=None):
        schema = self.schema.to_json_schema(parent)
        type_schema = schema.pop('type')
        schema['nullable'] = 'null' in type_schema
        if schema['nullable']:
            type_schema.remove('null')
            if len(type_schema) == 1:
                type_schema = type_schema[0]
        schema['anyOf'] = [{'type': type_schema}, {'type': 'string', 'enum': ['INHERIT']}]
        return schema


def _none(x):
    if x in (0, None):
        return 'none'
    return x


def _null(x):
    if x == 'none':
        return None
    return x


class ScrubError(CallError):
    pass


class PoolResilverModel(sa.Model):
    __tablename__ = 'storage_resilver'

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), default=True)
    begin = sa.Column(sa.Time(), default=time(hour=18))
    end = sa.Column(sa.Time(), default=time(hour=9))
    weekday = sa.Column(sa.String(120), default='1,2,3,4,5,6,7')


class PoolResilverService(ConfigService):

    class Config:
        namespace = 'pool.resilver'
        datastore = 'storage.resilver'
        datastore_extend = 'pool.resilver.resilver_extend'
        cli_namespace = 'storage.resilver'

    ENTRY = Dict(
        'pool_resilver_entry',
        Int('id', required=True),
        Str('begin', validators=[Time()], required=True),
        Str('end', validators=[Time()], required=True),
        Bool('enabled', required=True),
        List('weekday', required=True, items=[Int('weekday', validators=[Range(min=1, max=7)])])
    )

    @private
    async def resilver_extend(self, data):
        data['begin'] = data['begin'].strftime('%H:%M')
        data['end'] = data['end'].strftime('%H:%M')
        data['weekday'] = [int(v) for v in data['weekday'].split(',') if v]
        return data

    @private
    async def validate_fields_and_update(self, data, schema):
        verrors = ValidationErrors()

        begin = data.get('begin')
        if begin:
            data['begin'] = time(int(begin.split(':')[0]), int(begin.split(':')[1]))

        end = data.get('end')
        if end:
            data['end'] = time(int(end.split(':')[0]), int(end.split(':')[1]))

        weekdays = data.get('weekday')
        if not weekdays:
            verrors.add(
                f'{schema}.weekday',
                'At least one weekday should be selected'
            )
        else:
            data['weekday'] = ','.join([str(day) for day in weekdays])

        return verrors, data

    async def do_update(self, data):
        """
        Configure Pool Resilver Priority.

        If `begin` time is greater than `end` time it means it will rollover the day, e.g.
        begin = "19:00", end = "05:00" will increase pool resilver priority from 19:00 of one day
        until 05:00 of the next day.

        `weekday` follows crontab(5) values 0-7 (0 or 7 is Sun).

        .. examples(websocket)::

          Enable pool resilver priority all business days from 7PM to 5AM.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.resilver.update",
                "params": [{
                    "enabled": true,
                    "begin": "19:00",
                    "end": "05:00",
                    "weekday": [1, 2, 3, 4, 5]
                }]
            }
        """
        config = await self.config()
        original_config = config.copy()
        config.update(data)

        verrors, new_config = await self.validate_fields_and_update(config, 'pool_resilver_update')
        verrors.check()

        # before checking if any changes have been made, original_config needs to be mapped to new_config
        original_config['weekday'] = ','.join([str(day) for day in original_config['weekday']])
        original_config['begin'] = time(*(int(value) for value in original_config['begin'].split(':')))
        original_config['end'] = time(*(int(value) for value in original_config['end'].split(':')))
        if len(set(original_config.items()) ^ set(new_config.items())) > 0:
            # data has changed
            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                new_config['id'],
                new_config
            )

            await self.middleware.call('service.restart', 'cron')
            await self.middleware.call('pool.configure_resilver_priority')

        return await self.config()


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

    GELI_KEYPATH = '/data/geli'

    class Config:
        datastore = 'storage.volume'
        datastore_extend = 'pool.pool_extend'
        datastore_extend_context = 'pool.pool_extend_context'
        datastore_prefix = 'vol_'
        event_send = False
        cli_namespace = 'storage.pool'

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

    @item_method
    @accepts(
        Int('id', required=True),
        Str('action', enum=['START', 'STOP', 'PAUSE'], required=True)
    )
    @job(transient=True)
    async def scrub(self, job, oid, action):
        """
        Performs a scrub action to pool of `id`.

        `action` can be either of "START", "STOP" or "PAUSE".

        .. examples(websocket)::

          Start scrub on pool of id 1.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.scrub",
                "params": [1, "START"]
            }
        """
        pool = await self.get_instance(oid)
        return await job.wrap(
            await self.middleware.call('pool.scrub.scrub', pool['name'], action)
        )

    @accepts(List('types', items=[Str('type', enum=['FILESYSTEM', 'VOLUME'])], default=['FILESYSTEM', 'VOLUME']))
    @returns(List(items=[Str('filesystem_name')]))
    async def filesystem_choices(self, types):
        """
        Returns all available datasets, except the following:
            1. system datasets
            2. glusterfs datasets
            3. application(s) internal datasets

        .. examples(websocket)::

          Get all datasets.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.filesystem_choices",
                "params": []
            }

          Get only filesystems (exclude volumes).

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.filesystem_choices",
                "params": [["FILESYSTEM"]]
            }
        """
        vol_names = [vol['name'] for vol in (await self.query())]
        return [
            y['name'] for y in await self.middleware.call(
                'zfs.dataset.query',
                [
                    ('pool', 'in', vol_names),
                    ('type', 'in', types),
                ] + await self.middleware.call('pool.dataset.internal_datasets_filters'),
                {'extra': {'retrieve_properties': False}, 'order_by': ['name']},
            )
        ]

    @accepts(Int('id', required=True))
    @returns(Bool('pool_is_upgraded'))
    @item_method
    async def is_upgraded(self, oid):
        """
        Returns whether or not the pool of `id` is on the latest version and with all feature
        flags enabled.

        .. examples(websocket)::

          Check if pool of id 1 is upgraded.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.is_upgraded",
                "params": [1]
            }
        """
        return await self.is_upgraded_by_name((await self.get_instance(oid))['name'])

    @private
    async def is_upgraded_by_name(self, name):
        try:
            return await self.middleware.call('zfs.pool.is_upgraded', name)
        except CallError:
            return False

    @accepts(Int('id'))
    @returns(Bool('upgraded'))
    @item_method
    async def upgrade(self, oid):
        """
        Upgrade pool of `id` to latest version with all feature flags.

        .. examples(websocket)::

          Upgrade pool of id 1.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.upgrade",
                "params": [1]
            }
        """
        # Should we check first if upgrade is required ?
        await self.middleware.call(
            'zfs.pool.upgrade',
            (await self.get_instance(oid))['name']
        )
        return True

    @private
    def transform_topology(self, x, options=None):
        """
        Transform topology output from libzfs to add `device` and make `type` uppercase.
        """
        options = options or {}
        if isinstance(x, dict):
            if options.get('device_disk', True):
                path = x.get('path')
                if path is not None:
                    device = disk = None
                    if path.startswith('/dev/'):
                        args = [path[5:]]
                        device = self.middleware.call_sync('disk.label_to_dev', *args)
                        disk = self.middleware.call_sync('disk.label_to_disk', *args)
                    x['device'] = device
                    x['disk'] = disk

            if options.get('unavail_disk', True):
                guid = x.get('guid')
                if guid is not None:
                    unavail_disk = None
                    if x.get('status') != 'ONLINE':
                        unavail_disk = self.middleware.call_sync('disk.disk_by_zfs_guid', guid)
                    x['unavail_disk'] = unavail_disk

            for key in x:
                if key == 'type' and isinstance(x[key], str):
                    x[key] = x[key].upper()
                else:
                    x[key] = self.transform_topology(x[key], dict(options, geom_scan=False))
        elif isinstance(x, list):
            for i, entry in enumerate(x):
                x[i] = self.transform_topology(x[i], dict(options, geom_scan=False))
        return x

    @private
    async def transform_topology_lightweight(self, x):
        return await self.middleware.call('pool.transform_topology', x, {'device_disk': False, 'unavail_disk': False})

    @private
    def flatten_topology(self, topology):
        d = deque(sum(topology.values(), []))
        result = []
        while d:
            vdev = d.popleft()
            result.append(vdev)
            d.extend(vdev["children"])
        return result

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
            'compression': 'lz4',
            'aclinherit': 'passthrough',
            'mountpoint': f'/{data["name"]}',
            **encryption_dict
        }

        fsoptions['acltype'] = 'posix'
        fsoptions['aclmode'] = 'discard'

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
        asyncio.ensure_future(self.middleware.call('disk.swaps_configure'))
        asyncio.ensure_future(self.restart_services())

        pool = await self.get_instance(pool_id)
        await self.middleware.call_hook('pool.post_create', pool=pool)
        await self.middleware.call_hook('pool.post_create_or_update', pool=pool)
        await self.middleware.call_hook(
            'dataset.post_create', {'encrypted': bool(encryption_dict), **encrypted_dataset_data}
        )
        self.middleware.send_event('pool.query', 'ADDED', id=pool_id, fields=pool)
        return pool

    @private
    async def restart_services(self):
        await self.middleware.call('service.reload', 'disk')
        # regenerate crontab because of scrub
        await self.middleware.call('service.restart', 'cron')

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
                await self.middleware.call('disk.check_disks_availability', list(disks),
                                           data['allow_duplicate_serials'])
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

    @item_method
    @accepts(Int('id', required=False, default=None, null=True))
    @returns(List('pool_disks', items=[Str('disk')]))
    async def get_disks(self, oid):
        """
        Get all disks in use by pools.
        If `id` is provided only the disks from the given pool `id` will be returned.
        """
        disks = []
        for pool in await self.middleware.call('pool.query', [] if not oid else [('id', '=', oid)]):
            if pool['is_decrypted'] and pool['status'] != 'OFFLINE':
                disks.extend(await self.middleware.call('zfs.pool.get_disks', pool['name']))
        return disks

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
    ))
    @returns(Bool('detached'))
    async def detach(self, oid, options):
        """
        Detach a disk from pool of id `id`.

        `label` is the vdev guid or device name.

        .. examples(websocket)::

          Detach ZFS device.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.detach,
                "params": [1, {
                    "label": "80802394992848654"
                }]
            }
        """
        pool = await self.get_instance(oid)

        verrors = ValidationErrors()
        found = await self.middleware.call('pool.find_disk_from_topology', options['label'], pool)
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found on this pool.')
        verrors.check()

        disk = await self.middleware.call(
            'disk.label_to_disk', found[1]['path'].replace('/dev/', '')
        )
        if disk:
            await self.middleware.call('disk.swaps_remove_disks', [disk])

        await self.middleware.call('zfs.pool.detach', pool['name'], found[1]['guid'])

        if disk:
            wipe_job = await self.middleware.call('disk.wipe', disk, 'QUICK')
            await wipe_job.wait()
            if wipe_job.error:
                raise CallError(f'Failed to wipe disk {disk}: {wipe_job.error}')

        return True

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
    ))
    @returns(Bool('offline_successful'))
    async def offline(self, oid, options):
        """
        Offline a disk from pool of id `id`.

        `label` is the vdev guid or device name.

        .. examples(websocket)::

          Offline ZFS device.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.offline,
                "params": [1, {
                    "label": "80802394992848654"
                }]
            }
        """
        pool = await self.get_instance(oid)

        verrors = ValidationErrors()
        found = await self.middleware.call('pool.find_disk_from_topology', options['label'], pool)
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found on this pool.')
        verrors.check()

        disk = await self.middleware.call(
            'disk.label_to_disk', found[1]['path'].replace('/dev/', '')
        )
        if disk:
            await self.middleware.call('disk.swaps_remove_disks', [disk])

        await self.middleware.call('zfs.pool.offline', pool['name'], found[1]['guid'])

        return True

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
    ))
    @returns(Bool('online_successful'))
    async def online(self, oid, options):
        """
        Online a disk from pool of id `id`.

        `label` is the vdev guid or device name.

        .. examples(websocket)::

          Online ZFS device.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.online,
                "params": [1, {
                    "label": "80802394992848654"
                }]
            }
        """
        pool = await self.get_instance(oid)

        verrors = ValidationErrors()

        found = await self.middleware.call('pool.find_disk_from_topology', options['label'], pool)
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found on this pool.')
        verrors.check()

        await self.middleware.call('zfs.pool.online', pool['name'], found[1]['guid'])

        disk = await self.middleware.call(
            'disk.label_to_disk', found[1]['path'].replace('/dev/', '')
        )
        if disk:
            asyncio.ensure_future(self.middleware.call('disk.swaps_configure'))

        return True

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
    ))
    @returns()
    @job(lock=lambda args: f'{args[0]}_remove')
    async def remove(self, job, oid, options):
        """
        Remove a disk from pool of id `id`.

        `label` is the vdev guid or device name.

        Error codes:

            EZFS_NOSPC(2032): out of space to remove a device
            EZFS_NODEVICE(2017): no such device in pool
            EZFS_NOREPLICAS(2019): no valid replicas

        .. examples(websocket)::

          Remove ZFS device.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.remove,
                "params": [1, {
                    "label": "80802394992848654"
                }]
            }
        """
        pool = await self.get_instance(oid)

        verrors = ValidationErrors()

        found = await self.middleware.call('pool.find_disk_from_topology', options['label'], pool, True)
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found on this pool.')

        verrors.check()

        job.set_progress(20, f'Initiating removal of {options["label"]!r} ZFS device')
        await self.middleware.call('zfs.pool.remove', pool['name'], found[1]['guid'])
        job.set_progress(40, 'Waiting for removal of ZFS device to complete')
        # We would like to wait not for the removal to actually complete for cases where the removal might not
        # be synchronous like removing top level vdevs except for slog and l2arc
        await self.middleware.call('zfs.pool.wait', pool['name'], {'activity_type': 'REMOVE'})
        job.set_progress(60, 'Removal of ZFS device complete')

        if found[1]['type'] != 'DISK':
            disk_paths = [d['path'] for d in found[1]['children']]
        else:
            disk_paths = [found[1]['path']]

        wipe_jobs = []
        for disk_path in disk_paths:
            disk = await self.middleware.call(
                'disk.label_to_disk', disk_path.replace('/dev/', '')
            )
            if disk:
                wipe_job = await self.middleware.call('disk.wipe', disk, 'QUICK', False)
                wipe_jobs.append((disk, wipe_job))

        job.set_progress(70, 'Wiping disks')
        error_str = ''
        for index, item in enumerate(wipe_jobs):
            disk, wipe_job = item
            await wipe_job.wait()
            if wipe_job.error:
                error_str += f'{index + 1}) {disk}: {wipe_job.error}\n'

        if error_str:
            raise CallError(f'Failed to wipe disks:\n{error_str}')

        job.set_progress(100, 'Successfully completed wiping disks')

    @private
    def configure_resilver_priority(self):
        """
        Configure resilver priority based on user selected off-peak hours.
        """
        resilver = self.middleware.call_sync('datastore.config', 'storage.resilver')

        if not resilver['enabled'] or not resilver['weekday']:
            return

        higher_prio = False
        weekdays = map(lambda x: int(x), resilver['weekday'].split(','))
        now = datetime.now()
        now_t = now.time()
        # end overlaps the day
        if resilver['begin'] > resilver['end']:
            if now.isoweekday() in weekdays and now_t >= resilver['begin']:
                higher_prio = True
            else:
                lastweekday = now.isoweekday() - 1
                if lastweekday == 0:
                    lastweekday = 7
                if lastweekday in weekdays and now_t < resilver['end']:
                    higher_prio = True
        # end does not overlap the day
        else:
            if now.isoweekday() in weekdays and now_t >= resilver['begin'] and now_t < resilver['end']:
                higher_prio = True

        if higher_prio:
            resilver_min_time_ms = 9000
            nia_credit = 10
            nia_delay = 2
            scrub_max_active = 8
        else:
            resilver_min_time_ms = 3000
            nia_credit = 5
            nia_delay = 5
            scrub_max_active = 3

        with open('/sys/module/zfs/parameters/zfs_resilver_min_time_ms', 'w') as f:
            f.write(str(resilver_min_time_ms))
        with open('/sys/module/zfs/parameters/zfs_vdev_nia_credit', 'w') as f:
            f.write(str(nia_credit))
        with open('/sys/module/zfs/parameters/zfs_vdev_nia_delay', 'w') as f:
            f.write(str(nia_delay))
        with open('/sys/module/zfs/parameters/zfs_vdev_scrub_max_active', 'w') as f:
            f.write(str(scrub_max_active))

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
            'sharenfs': {'value': "off"}, 'sharesmb': {'value': "off"},
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

        asyncio.ensure_future(self.middleware.call('service.restart', 'collectd'))
        await self.middleware.call_hook('pool.post_import', {'passphrase': data.get('passphrase'), **pool})
        await self.middleware.call('pool.dataset.sync_db_keys', pool['name'])
        self.middleware.send_event('pool.query', 'ADDED', id=pool_id, fields=pool)

        return True

    @item_method
    @accepts(
        Int('id'),
        Dict(
            'options',
            Bool('cascade', default=False),
            Bool('restart_services', default=False),
            Bool('destroy', default=False),
        ),
    )
    @returns()
    @job(lock='pool_export')
    async def export(self, job, oid, options):
        """
        Export pool of `id`.

        `cascade` will delete all attachments of the given pool (`pool.attachments`).
        `restart_services` will restart services that have open files on given pool.
        `destroy` will also PERMANENTLY destroy the pool/data.

        .. examples(websocket)::

          Export pool of id 1.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.export,
                "params": [1, {
                    "cascade": true,
                    "destroy": false
                }]
            }

        If this is an HA system and failover is enabled and the last zpool is
        exported/disconnected, then this will raise EOPNOTSUPP. Failover must
        be disabled before exporting the last zpool on the system.
        """
        pool = await self.get_instance(oid)
        root_ds = await self.middleware.call('pool.dataset.query', [['id', '=', pool['name']]])
        if root_ds and root_ds[0]['locked'] and os.path.exists(root_ds[0]['mountpoint']):
            # We should be removing immutable flag in this case if the path exists
            await self.middleware.call('filesystem.set_immutable', False, root_ds[0]['mountpoint'])

        pool_count = await self.middleware.call('pool.query', [], {'count': True})
        if pool_count == 1 and await self.middleware.call('failover.licensed'):
            if not (await self.middleware.call('failover.config'))['disabled']:
                err = errno.EOPNOTSUPP
                raise CallError('Disable failover before exporting last pool on system.', err)

        enable_on_import_key = f'pool:{pool["name"]}:enable_on_import'
        enable_on_import = {}
        if not options['cascade']:
            if await self.middleware.call('keyvalue.has_key', enable_on_import_key):
                enable_on_import = await self.middleware.call('keyvalue.get', enable_on_import_key)

        for i, delegate in enumerate(PoolDatasetService.attachment_delegates):
            job.set_progress(
                i, f'{"Deleting" if options["cascade"] else "Disabling"} pool attachments: {delegate.title}')

            attachments = await delegate.query(pool['path'], True)
            if attachments:
                if options["cascade"]:
                    await delegate.delete(attachments)
                else:
                    await delegate.toggle(attachments, False)
                    enable_on_import[delegate.name] = list(
                        set(enable_on_import.get(delegate.name, [])) |
                        {attachment['id'] for attachment in attachments}
                    )

        if enable_on_import:
            await self.middleware.call('keyvalue.set', enable_on_import_key, enable_on_import)
        else:
            await self.middleware.call('keyvalue.delete', enable_on_import_key)

        job.set_progress(20, 'Terminating processes that are using this pool')
        try:
            await self.middleware.call('pool.dataset.kill_processes', pool['name'],
                                       options.get('restart_services', False))
        except ValidationError as e:
            if e.errno == errno.ENOENT:
                # Dataset might not exist (e.g. pool is not decrypted), this is not an error
                pass
            else:
                raise

        await self.middleware.call('iscsi.global.terminate_luns_for_pool', pool['name'])

        job.set_progress(30, 'Removing pool disks from swap')
        disks = await self.middleware.call('pool.get_disks', oid)

        # We don't want to configure swap immediately after removing those disks because we might get in a race
        # condition where swap starts using the pool disks as the pool might not have been exported/destroyed yet
        await self.middleware.call('disk.swaps_remove_disks', disks, {'configure_swap': False})

        await self.middleware.call_hook('pool.pre_export', pool=pool['name'], options=options, job=job)

        if pool['status'] == 'OFFLINE':
            # Pool exists only in database, its not imported
            pass
        elif options['destroy']:
            job.set_progress(60, 'Destroying pool')
            await self.middleware.call('zfs.pool.delete', pool['name'])

            job.set_progress(80, 'Cleaning disks')

            async def unlabel(disk):
                wipe_job = await self.middleware.call(
                    'disk.wipe', disk, 'QUICK', False, {'configure_swap': False}
                )
                await wipe_job.wait()
                if wipe_job.error:
                    self.logger.warning(f'Failed to wipe disk {disk}: {wipe_job.error}')
            await asyncio_map(unlabel, disks, limit=16)

            await self.middleware.call('disk.sync_all')

            if pool['encrypt'] > 0:
                try:
                    os.remove(pool['encryptkey_path'])
                except OSError as e:
                    self.logger.warning(
                        'Failed to remove encryption key %s: %s',
                        pool['encryptkey_path'],
                        e,
                        exc_info=True,
                    )
        else:
            job.set_progress(80, 'Exporting pool')
            await self.middleware.call('zfs.pool.export', pool['name'])

        job.set_progress(90, 'Cleaning up')
        if os.path.isdir(pool['path']):
            try:
                # We dont try to remove recursively to avoid removing files that were
                # potentially hidden by the mount
                os.rmdir(pool['path'])
            except OSError as e:
                self.logger.warning('Failed to remove mountpoint %s: %s', pool['path'], e)

        await self.middleware.call('datastore.delete', 'storage.volume', oid)
        await self.middleware.call(
            'pool.dataset.delete_encrypted_datasets_from_db',
            [['OR', [['name', '=', pool['name']], ['name', '^', f'{pool["name"]}/']]]],
        )
        await self.middleware.call_hook('dataset.post_delete', pool['name'])

        # scrub needs to be regenerated in crontab
        await self.middleware.call('service.restart', 'cron')

        # Let's reconfigure swap in case dumpdev needs to be configured again
        asyncio.ensure_future(self.middleware.call('disk.swaps_configure'))

        await self.middleware.call_hook('pool.post_export', pool=pool['name'], options=options)
        self.middleware.send_event('pool.query', 'CHANGED', id=oid, cleared=True)
        self.middleware.send_event('pool.query', 'REMOVED', id=oid)

    @item_method
    @accepts(Int('id'))
    @returns(List(items=[Dict(
        'attachment',
        Str('type', required=True),
        Str('service', required=True, null=True),
        List('attachments', items=[Str('attachment_name')]),
    )], register=True))
    async def attachments(self, oid):
        """
        Return a list of services dependent of this pool.

        Responsible for telling the user whether there is a related
        share, asking for confirmation.
        """
        pool = await self.get_instance(oid)
        return await self.middleware.call('pool.dataset.attachments_with_path', pool['path'])

    @item_method
    @accepts(Int('id'))
    @returns(List(items=[Dict(
        'process',
        Int('pid', required=True),
        Str('name', required=True),
        Str('service'),
        Str('cmdline', max_length=None),
    )], register=True))
    async def processes(self, oid):
        """
        Returns a list of running processes using this pool.
        """
        pool = await self.get_instance(oid)
        processes = []
        try:
            processes = await self.middleware.call('pool.dataset.processes', pool['name'])
        except ValidationError as e:
            if e.errno == errno.ENOENT:
                # Dataset might not exist (e.g. not online), this is not an error
                pass
            else:
                raise

        return processes

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

    """
    These methods are hacks for old UI which supports only one volume import at a time
    """


class PoolDatasetUserPropService(CRUDService):

    class Config:
        datastore_primary_key_type = 'string'
        namespace = 'pool.dataset.userprop'
        cli_namespace = 'storage.dataset.user_prop'

    ENTRY = Dict(
        'pool_dataset_userprop_entry',
        Str('id', required=True),
        Dict('properties', additional_attrs=True, required=True),
    )

    @filterable
    def query(self, filters, options):
        """
        Query all user properties for ZFS datasets.
        """
        return filter_list(
            [
                {k: d[k] for k in ('id', 'properties')} for d in
                (self.middleware.call_sync('zfs.dataset.query', [], {
                    'extra': {'user_properties': True, 'properties': []}
                }))
            ], filters, options
        )

    async def __common_validation(self, dataset, data, schema, update=False):
        verrors = ValidationErrors()
        exists = data['name'] in dataset['properties']
        if (exists and not update) or (not exists and update):
            if update:
                msg = f'{data["name"]} does not exist in {dataset["id"]} user properties'
            else:
                msg = f'{data["name"]} exists in {dataset["id"]} user properties'
            verrors.add(f'{schema}.property.name', msg)

        return verrors

    @accepts(
        Dict(
            'dataset_user_prop_create',
            Str('id', required=True, empty=False),
            Dict(
                'property',
                Str('name', required=True, validators=[Match(r'.*:.*')]),
                Str('value', required=True),
            )
        )
    )
    async def do_create(self, data):
        """
        Create a user property for a given `id` dataset.
        """
        dataset = await self.get_instance(data['id'])
        verrors = await self.__common_validation(dataset, data['property'], 'dataset_user_prop_create')
        verrors.check()

        await self.middleware.call(
            'zfs.dataset.update', data['id'], {
                'properties': {data['property']['name']: {'value': data['property']['value']}}
            }
        )

        return await self.get_instance(data['id'])

    @accepts(
        Str('id'),
        Dict(
            'dataset_user_prop_update',
            Str('name', required=True),
            Str('value', required=True),
        )
    )
    async def do_update(self, id, data):
        """
        Update `dataset_user_prop_update.name` user property for `id` dataset.
        """
        dataset = await self.get_instance(id)
        verrors = await self.__common_validation(dataset, data, 'dataset_user_prop_update', True)
        verrors.check()

        await self.middleware.call(
            'zfs.dataset.update', id, {
                'properties': {data['name']: {'value': data['value']}}
            }
        )

        return await self.get_instance(id)

    @accepts(
        Str('id'),
        Dict(
            'dataset_user_prop_delete',
            Str('name', required=True),
        )
    )
    async def do_delete(self, id, options):
        """
        Delete user property `dataset_user_prop_delete.name` for `id` dataset.
        """
        dataset = await self.get_instance(id)
        verrors = await self.__common_validation(dataset, options, 'dataset_user_prop_delete', True)
        verrors.check()

        await self.middleware.call(
            'zfs.dataset.update', id, {
                'properties': {options['name']: {'source': 'INHERIT'}}
            }
        )
        return True


class PoolDatasetEncryptionModel(sa.Model):
    __tablename__ = 'storage_encrypteddataset'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255))
    encryption_key = sa.Column(sa.EncryptedText(), nullable=True)
    kmip_uid = sa.Column(sa.String(255), nullable=True, default=None)


def get_props_of_interest_mapping():
    return [
        ('org.freenas:description', 'comments', None),
        ('org.freenas:quota_warning', 'quota_warning', None),
        ('org.freenas:quota_critical', 'quota_critical', None),
        ('org.freenas:refquota_warning', 'refquota_warning', None),
        ('org.freenas:refquota_critical', 'refquota_critical', None),
        ('org.truenas:managedby', 'managedby', None),
        ('dedup', 'deduplication', str.upper),
        ('mountpoint', None, _null),
        ('aclmode', None, str.upper),
        ('acltype', None, str.upper),
        ('xattr', None, str.upper),
        ('atime', None, str.upper),
        ('casesensitivity', None, str.upper),
        ('checksum', None, str.upper),
        ('exec', None, str.upper),
        ('sync', None, str.upper),
        ('compression', None, str.upper),
        ('compressratio', None, None),
        ('origin', None, None),
        ('quota', None, _null),
        ('refquota', None, _null),
        ('reservation', None, _null),
        ('refreservation', None, _null),
        ('copies', None, None),
        ('snapdir', None, str.upper),
        ('readonly', None, str.upper),
        ('recordsize', None, None),
        ('sparse', None, None),
        ('volsize', None, None),
        ('volblocksize', None, None),
        ('keyformat', 'key_format', lambda o: o.upper() if o != 'none' else None),
        ('encryption', 'encryption_algorithm', lambda o: o.upper() if o != 'off' else None),
        ('used', None, None),
        ('usedbychildren', None, None),
        ('usedbydataset', None, None),
        ('usedbyrefreservation', None, None),
        ('usedbysnapshots', None, None),
        ('available', None, None),
        ('special_small_blocks', 'special_small_block_size', None),
        ('pbkdf2iters', None, None),
        ('creation', None, None),
        ('snapdev', None, str.upper),
    ]


class PoolDatasetService(CRUDService):

    attachment_delegates = []
    dataset_store = 'storage.encrypteddataset'
    ENTRY = Dict(
        'pool_dataset_entry',
        Str('id', required=True),
        Str('type', required=True),
        Str('name', required=True),
        Str('pool', required=True),
        Bool('encrypted'),
        Str('encryption_root', null=True),
        Bool('key_loaded', null=True),
        List('children', required=True),
        Dict('user_properties', additional_attrs=True, required=True),
        Bool('locked'),
        *[Dict(
            p[1] or p[0],
            Any('parsed', null=True),
            Str('rawvalue', null=True),
            Str('value', null=True),
            Str('source', null=True),
            Any('source_info', null=True),
        ) for p in get_props_of_interest_mapping() if (p[1] or p[0]) != 'mountpoint'],
        Str('mountpoint', null=True),
    )

    class Config:
        datastore_primary_key_type = 'string'
        namespace = 'pool.dataset'
        event_send = False
        cli_namespace = 'storage.dataset'

    @accepts()
    @returns(Dict(
        *[Str(k, enum=[k]) for k in ZFS_CHECKSUM_CHOICES if k != 'OFF'],
    ))
    async def checksum_choices(self):
        """
        Retrieve checksums supported for ZFS dataset.
        """
        return {v: v for v in ZFS_CHECKSUM_CHOICES if v != 'OFF'}

    @accepts()
    @returns(Dict(
        *[Str(k, enum=[k]) for k in ZFS_COMPRESSION_ALGORITHM_CHOICES],
    ))
    async def compression_choices(self):
        """
        Retrieve compression algorithm supported by ZFS.
        """
        return {v: v for v in ZFS_COMPRESSION_ALGORITHM_CHOICES}

    @accepts()
    @returns(Dict(
        *[Str(k, enum=[k]) for k in ZFS_ENCRYPTION_ALGORITHM_CHOICES],
    ))
    async def encryption_algorithm_choices(self):
        """
        Retrieve encryption algorithms supported for ZFS dataset encryption.
        """
        return {v: v for v in ZFS_ENCRYPTION_ALGORITHM_CHOICES}

    @private
    @accepts(
        Dict(
            'dataset_db_create',
            Any('encryption_key', null=True, default=None),
            Int('id', default=None, null=True),
            Str('name', required=True, empty=False),
            Str('key_format', required=True, null=True),
        )
    )
    async def insert_or_update_encrypted_record(self, data):
        key_format = data.pop('key_format') or ZFSKeyFormat.PASSPHRASE.value
        if not data['encryption_key'] or ZFSKeyFormat(key_format.upper()) == ZFSKeyFormat.PASSPHRASE:
            # We do not want to save passphrase keys - they are only known to the user
            return

        ds_id = data.pop('id')
        ds = await self.middleware.call(
            'datastore.query', self.dataset_store,
            [['id', '=', ds_id]] if ds_id else [['name', '=', data['name']]]
        )

        data['encryption_key'] = data['encryption_key']

        pk = ds[0]['id'] if ds else None
        if ds:
            await self.middleware.call(
                'datastore.update',
                self.dataset_store,
                ds[0]['id'], data
            )
        else:
            pk = await self.middleware.call(
                'datastore.insert',
                self.dataset_store,
                data
            )

        kmip_config = await self.middleware.call('kmip.config')
        if kmip_config['enabled'] and kmip_config['manage_zfs_keys']:
            await self.middleware.call('kmip.sync_zfs_keys', [pk])

        return pk

    @private
    @accepts(Ref('query-filters'))
    def query_encrypted_roots_keys(self, filters):
        # We query database first - if we are able to find an encryption key, we assume it's the correct one.
        # If we are unable to find the key in database, we see if we have it in memory with the KMIP server, if not,
        # there are 2 ways this can go, we don't retrieve the key or the user can sync KMIP keys and we will have it
        # with the KMIP service again through which we can retrieve them
        datasets = filter_list(self.middleware.call_sync('datastore.query', self.dataset_store), filters)
        zfs_keys = self.middleware.call_sync('kmip.retrieve_zfs_keys')
        keys = {}
        for ds in datasets:
            if ds['encryption_key']:
                keys[ds['name']] = ds['encryption_key']
            elif ds['name'] in zfs_keys:
                keys[ds['name']] = zfs_keys[ds['name']]
        return keys

    @private
    def validate_encryption_data(self, job, verrors, encryption_dict, schema):
        opts = {}
        if not encryption_dict['enabled']:
            return opts

        key = encryption_dict['key']
        passphrase = encryption_dict['passphrase']
        passphrase_key_format = bool(encryption_dict['passphrase'])

        if passphrase_key_format:
            for f in filter(lambda k: encryption_dict[k], ('key', 'key_file', 'generate_key')):
                verrors.add(f'{schema}.{f}', 'Must be disabled when dataset is to be encrypted with passphrase.')
        else:
            provided_opts = [k for k in ('key', 'key_file', 'generate_key') if encryption_dict[k]]
            if not provided_opts:
                verrors.add(
                    f'{schema}.key',
                    'Please provide a key or select generate_key to automatically generate '
                    'a key when passphrase is not provided.'
                )
            elif len(provided_opts) > 1:
                for k in provided_opts:
                    verrors.add(f'{schema}.{k}', f'Only one of {", ".join(provided_opts)} must be provided.')

        if not verrors:
            key = key or passphrase
            if encryption_dict['generate_key']:
                key = secrets.token_hex(32)
            elif not key and job:
                job.check_pipe('input')
                key = job.pipes.input.r.read(64)
                # We would like to ensure key matches specified key format
                try:
                    key = hex(int(key, 16))[2:]
                    if len(key) != 64:
                        raise ValueError('Invalid key')
                except ValueError:
                    verrors.add(f'{schema}.key_file', 'Please specify a valid key')
                    return {}

            opts = {
                'keyformat': (ZFSKeyFormat.PASSPHRASE if passphrase_key_format else ZFSKeyFormat.HEX).value.lower(),
                'keylocation': 'prompt',
                'encryption': encryption_dict['algorithm'].lower(),
                'key': key,
                **({'pbkdf2iters': encryption_dict['pbkdf2iters']} if passphrase_key_format else {}),
            }
        return opts

    @private
    def query_encrypted_datasets(self, name, options=None):
        # Common function to retrieve encrypted datasets
        options = options or {}
        key_loaded = options.get('key_loaded', True)
        db_results = self.query_encrypted_roots_keys([['OR', [['name', '=', name], ['name', '^', f'{name}/']]]])

        def normalize(ds):
            passphrase = ZFSKeyFormat(ds['key_format']['value']) == ZFSKeyFormat.PASSPHRASE
            key = db_results.get(ds['name']) if not passphrase else None
            return ds['name'], {'encryption_key': key, **ds}

        def check_key(ds):
            return options.get('all') or (ds['key_loaded'] and key_loaded) or (not ds['key_loaded'] and not key_loaded)

        return dict(map(
            normalize,
            filter(
                lambda d: d['name'] == d['encryption_root'] and d['encrypted'] and
                f'{d["name"]}/'.startswith(f'{name}/') and check_key(d),
                self.query()
            )
        ))

    @periodic(86400)
    @private
    @job(lock=lambda args: f'sync_encrypted_pool_dataset_keys_{args}')
    def sync_db_keys(self, job, name=None):
        if not self.middleware.call_sync('failover.is_single_master_node'):
            # We don't want to do this for passive controller
            return
        filters = [['OR', [['name', '=', name], ['name', '^', f'{name}/']]]] if name else []

        # It is possible we have a pool configured but for some mistake/reason the pool did not import like
        # during repair disks were not plugged in and system was booted, in such cases we would like to not
        # remove the encryption keys from the database.
        for root_ds in {pool['name'] for pool in self.middleware.call_sync('pool.query')} - {
            ds['id'] for ds in self.middleware.call_sync(
                'pool.dataset.query', [], {'extra': {'retrieve_children': False, 'properties': []}}
            )
        }:
            filters.extend([['name', '!=', root_ds], ['name', '!^', f'{root_ds}/']])

        db_datasets = self.query_encrypted_roots_keys(filters)
        encrypted_roots = {
            d['name']: d for d in self.query(filters, {'extra': {'properties': ['encryptionroot']}})
            if d['name'] == d['encryption_root']
        }
        to_remove = []
        check_key_job = self.middleware.call_sync('zfs.dataset.bulk_process', 'check_key', [
            (name, {'key': db_datasets[name]}) for name in db_datasets
        ])
        check_key_job.wait_sync()
        if check_key_job.error:
            self.logger.error(f'Failed to sync database keys: {check_key_job.error}')
            return

        for dataset, status in zip(db_datasets, check_key_job.result):
            if not status['result']:
                to_remove.append(dataset)
            elif status['error']:
                if dataset not in encrypted_roots:
                    to_remove.append(dataset)
                else:
                    self.logger.error(f'Failed to check encryption status for {dataset}: {status["error"]}')

        self.middleware.call_sync('pool.dataset.delete_encrypted_datasets_from_db', [['name', 'in', to_remove]])

    @private
    async def delete_encrypted_datasets_from_db(self, filters):
        datasets = await self.middleware.call('datastore.query', self.dataset_store, filters)
        for ds in datasets:
            if ds['kmip_uid']:
                asyncio.ensure_future(self.middleware.call('kmip.reset_zfs_key', ds['name'], ds['kmip_uid']))
            await self.middleware.call('datastore.delete', self.dataset_store, ds['id'])

    @accepts(Str('id'))
    @returns()
    @job(lock='dataset_export_keys', pipes=['output'])
    def export_keys(self, job, id):
        """
        Export keys for `id` and its children which are stored in the system. The exported file is a JSON file
        which has a dictionary containing dataset names as keys and their keys as the value.

        Please refer to websocket documentation for downloading the file.
        """
        self.middleware.call_sync('pool.dataset.get_instance', id)
        sync_job = self.middleware.call_sync('pool.dataset.sync_db_keys', id)
        sync_job.wait_sync()

        datasets = self.query_encrypted_roots_keys([['OR', [['name', '=', id], ['name', '^', f'{id}/']]]])
        with BytesIO(json.dumps(datasets).encode()) as f:
            shutil.copyfileobj(f, job.pipes.output.w)

    @accepts(
        Str('id'),
        Bool('download', default=False),
    )
    @returns(Str('key', null=True, private=True))
    @job(lock='dataset_export_keys', pipes=['output'], check_pipes=False)
    def export_key(self, job, id, download):
        """
        Export own encryption key for dataset `id`. If `download` is `true`, key will be downloaded in a json file
        where the same file can be used to unlock the dataset, otherwise it will be returned as string.

        Please refer to websocket documentation for downloading the file.
        """
        if download:
            job.check_pipe('output')

        self.middleware.call_sync('pool.dataset.get_instance', id)

        keys = self.query_encrypted_roots_keys([['name', '=', id]])
        if id not in keys:
            raise CallError('Specified dataset does not have it\'s own encryption key.', errno.EINVAL)

        key = keys[id]

        if download:
            job.pipes.output.w.write(json.dumps({id: key}).encode())
        else:
            return key

    @accepts(
        Str('id'),
        Dict(
            'lock_options',
            Bool('force_umount', default=False),
        )
    )
    @returns(Bool('locked'))
    @job(lock=lambda args: 'dataset_lock')
    async def lock(self, job, id, options):
        """
        Locks `id` dataset. It will unmount the dataset and its children before locking.

        After the dataset has been unmounted, system will set immutable flag on the dataset's mountpoint where
        the dataset was mounted before it was locked making sure that the path cannot be modified. Once the dataset
        is unlocked, it will not be affected by this change and consumers can continue consuming it.
        """
        ds = await self.get_instance(id)

        if not ds['encrypted']:
            raise CallError(f'{id} is not encrypted')
        elif ds['locked']:
            raise CallError(f'Dataset {id} is already locked')
        elif ZFSKeyFormat(ds['key_format']['value']) != ZFSKeyFormat.PASSPHRASE:
            raise CallError('Only datasets which are encrypted with passphrase can be locked')
        elif id != ds['encryption_root']:
            raise CallError(f'Please lock {ds["encryption_root"]}. Only encryption roots can be locked.')

        async def detach(delegate):
            await delegate.stop(await delegate.query(self.__attachments_path(ds), True))

        try:
            await self.middleware.call('cache.put', 'about_to_lock_dataset', id)

            coroutines = [detach(dg) for dg in self.attachment_delegates]
            await asyncio.gather(*coroutines)

            await self.middleware.call(
                'zfs.dataset.unload_key', id, {
                    'umount': True, 'force_umount': options['force_umount'], 'recursive': True
                }
            )
        finally:
            await self.middleware.call('cache.pop', 'about_to_lock_dataset')

        if ds['mountpoint']:
            await self.middleware.call('filesystem.set_immutable', True, ds['mountpoint'])

        await self.middleware.call_hook('dataset.post_lock', id)

        return True

    @accepts(
        Str('id'),
        Dict(
            'unlock_options',
            Bool('force', default=False),
            Bool('key_file', default=False),
            Bool('recursive', default=False),
            Bool('toggle_attachments', default=True),
            List(
                'datasets', items=[
                    Dict(
                        'dataset',
                        Bool('force', required=True, default=False),
                        Str('name', required=True, empty=False),
                        Str('key', validators=[Range(min=64, max=64)], private=True),
                        Str('passphrase', empty=False, private=True),
                        Bool('recursive', default=False),
                    )
                ],
            ),
        )
    )
    @returns(Dict(
        List('unlocked', items=[Str('dataset')], required=True),
        Dict(
            'failed',
            required=True,
            additional_attrs=True,
            example={'vol1/enc': {'error': 'Invalid Key', 'skipped': []}},
        ),
    ))
    @job(lock=lambda args: f'dataset_unlock_{args[0]}', pipes=['input'], check_pipes=False)
    def unlock(self, job, id, options):
        """
        Unlock dataset `id` (and its children if `unlock_options.recursive` is `true`).

        If `id` dataset is not encrypted an exception will be raised. There is one exception:
        when `id` is a root dataset and `unlock_options.recursive` is specified, encryption
        validation will not be performed for `id`. This allow unlocking encrypted children for the entire pool `id`.

        There are two ways to supply the key(s)/passphrase(s) for unlocking a dataset:

        1. Upload a json file which contains encrypted dataset keys (it will be read from the input pipe if
        `unlock_options.key_file` is `true`). The format is the one that is used for exporting encrypted dataset keys
        (`pool.export_keys`).

        2. Specify a key or a passphrase for each unlocked dataset using `unlock_options.datasets`.

        If `unlock_options.datasets.{i}.recursive` is `true`, a key or a passphrase is applied to all the encrypted
        children of a dataset.

        `unlock_options.toggle_attachments` controls whether attachments  should be put in action after unlocking
        dataset(s). Toggling attachments can theoretically lead to service interruption when daemons configurations are
        reloaded (this should not happen,  and if this happens it should be considered a bug). As TrueNAS does not have
        a state for resources that should be unlocked but are still locked, disabling this option will put the system
        into an inconsistent state so it should really never be disabled.

        In some cases it's possible that the provided key/passphrase is valid but the path where the dataset is
        supposed to be mounted after being unlocked already exists and is not empty. In this case, unlock operation
        would fail. This can be overridden by setting `unlock_options.datasets.X.force` boolean flag or by setting
        `unlock_options.force` flag. When any of these flags are set, system will rename the existing
        directory/file path where the dataset should be mounted resulting in successful unlock of the dataset.
        """
        verrors = ValidationErrors()
        dataset = self.middleware.call_sync('pool.dataset.get_instance', id)
        keys_supplied = {}

        if options['key_file']:
            keys_supplied = self._retrieve_keys_from_file(job)

        for i, ds in enumerate(options['datasets']):
            if all(ds.get(k) for k in ('key', 'passphrase')):
                verrors.add(
                    f'unlock_options.datasets.{i}.dataset.key',
                    f'Must not be specified when passphrase for {ds["name"]} is supplied'
                )
            elif not any(ds.get(k) for k in ('key', 'passphrase')):
                verrors.add(
                    f'unlock_options.datasets.{i}.dataset',
                    f'Passphrase or key must be specified for {ds["name"]}'
                )

            if not options['force'] and not ds['force']:
                if err := self.dataset_can_be_mounted(ds['name'], os.path.join('/mnt', ds['name'])):
                    verrors.add(f'unlock_options.datasets.{i}.force', err)

            keys_supplied[ds['name']] = ds.get('key') or ds.get('passphrase')

        if '/' in id or not options['recursive']:
            if not dataset['locked']:
                verrors.add('id', f'{id} dataset is not locked')
            elif dataset['encryption_root'] != id:
                verrors.add('id', 'Only encryption roots can be unlocked')
            else:
                if not bool(self.query_encrypted_roots_keys([['name', '=', id]])) and id not in keys_supplied:
                    verrors.add('unlock_options.datasets', f'Please specify key for {id}')

        verrors.check()

        locked_datasets = []
        datasets = self.query_encrypted_datasets(id.split('/', 1)[0], {'key_loaded': False})
        self._assign_supplied_recursive_keys(options['datasets'], keys_supplied, list(datasets.keys()))
        for name, ds in datasets.items():
            ds_key = keys_supplied.get(name) or ds['encryption_key']
            if ds['locked'] and id.startswith(f'{name}/'):
                # This ensures that `id` has locked parents and they should be unlocked first
                locked_datasets.append(name)
            elif ZFSKeyFormat(ds['key_format']['value']) == ZFSKeyFormat.RAW and ds_key:
                # This is hex encoded right now - we want to change it back to raw
                try:
                    ds_key = bytes.fromhex(ds_key)
                except ValueError:
                    ds_key = None

            datasets[name] = {'key': ds_key, **ds}

        if locked_datasets:
            raise CallError(f'{id} has locked parents {",".join(locked_datasets)} which must be unlocked first')

        failed = defaultdict(lambda: dict({'error': None, 'skipped': []}))
        unlocked = []
        names = sorted(
            filter(
                lambda n: n and f'{n}/'.startswith(f'{id}/') and datasets[n]['locked'],
                (datasets if options['recursive'] else [id])
            ),
            key=lambda v: v.count('/')
        )
        for name_i, name in enumerate(names):
            skip = False
            for i in range(name.count('/') + 1):
                check = name.rsplit('/', i)[0]
                if check in failed:
                    failed[check]['skipped'].append(name)
                    skip = True
                    break

            if skip:
                continue

            if not datasets[name]['key']:
                failed[name]['error'] = 'Missing key'
                continue

            job.set_progress(int(name_i / len(names) * 90 + 0.5), f'Unlocking {name!r}')
            try:
                self.middleware.call_sync(
                    'zfs.dataset.load_key', name, {'key': datasets[name]['key'], 'mount': False}
                )
            except CallError as e:
                failed[name]['error'] = 'Invalid Key' if 'incorrect key provided' in str(e).lower() else str(e)
            else:
                # Before we mount the dataset in question, we should ensure that the path where it will be mounted
                # is not already being used by some other service/share. In this case, we should simply rename the
                # directory where it will be mounted

                mount_path = os.path.join('/mnt', name)
                if os.path.exists(mount_path):
                    try:
                        self.middleware.call_sync('filesystem.set_immutable', False, mount_path)
                    except OSError as e:
                        # It's ok to get `EROFS` because the dataset can have `readonly=on`
                        if e.errno != errno.EROFS:
                            raise
                    except Exception as e:
                        failed[name]['error'] = (
                            f'Dataset mount failed because immutable flag at {mount_path!r} could not be removed: {e}'
                        )
                        continue

                    if not os.path.isdir(mount_path) or os.listdir(mount_path):
                        # rename please
                        shutil.move(mount_path, f'{mount_path}-{str(uuid.uuid4())[:4]}-{datetime.now().isoformat()}')

                try:
                    self.middleware.call_sync('zfs.dataset.mount', name, {'recursive': True})
                except CallError as e:
                    failed[name]['error'] = f'Failed to mount dataset: {e}'
                else:
                    unlocked.append(name)

        for failed_ds in failed:
            failed_datasets = {}
            for ds in [failed_ds] + failed[failed_ds]['skipped']:
                mount_path = os.path.join('/mnt', ds)
                if os.path.exists(mount_path):
                    try:
                        self.middleware.call_sync('filesystem.set_immutable', True, mount_path)
                    except OSError as e:
                        # It's ok to get `EROFS` because the dataset can have `readonly=on`
                        if e.errno != errno.EROFS:
                            raise
                    except Exception as e:
                        failed_datasets[ds] = str(e)

            if failed_datasets:
                failed[failed_ds]['error'] += '\n\nFailed to set immutable flag on following datasets:\n' + '\n'.join(
                    f'{i + 1}) {ds!r}: {failed_datasets[ds]}' for i, ds in enumerate(failed_datasets)
                )

        services_to_restart = set()
        if self.middleware.call_sync('system.ready'):
            services_to_restart.add('disk')

        if unlocked:
            if options['toggle_attachments']:
                job.set_progress(91, 'Handling attachments')
                self.middleware.call_sync('pool.dataset.unlock_handle_attachments', dataset, options)

            job.set_progress(92, 'Updating database')

            def dataset_data(unlocked_dataset):
                return {
                    'encryption_key': keys_supplied.get(unlocked_dataset), 'name': unlocked_dataset,
                    'key_format': datasets[unlocked_dataset]['key_format']['value'],
                }

            for unlocked_dataset in filter(lambda d: d in keys_supplied, unlocked):
                self.middleware.call_sync(
                    'pool.dataset.insert_or_update_encrypted_record', dataset_data(unlocked_dataset)
                )

            job.set_progress(93, 'Restarting services')
            self.middleware.call_sync('pool.dataset.restart_services_after_unlock', id, services_to_restart)

            job.set_progress(94, 'Running post-unlock tasks')
            self.middleware.call_hook_sync(
                'dataset.post_unlock', datasets=[dataset_data(ds) for ds in unlocked],
            )

        return {'unlocked': unlocked, 'failed': failed}

    def _assign_supplied_recursive_keys(self, request_datasets, keys_supplied, queried_datasets):
        request_datasets = {ds['name']: ds for ds in request_datasets}
        for name in queried_datasets:
            if name not in keys_supplied:
                for parent in Path(name).parents:
                    parent = str(parent)
                    if parent in request_datasets and request_datasets[parent]['recursive']:
                        if parent in keys_supplied:
                            keys_supplied[name] = keys_supplied[parent]
                            break

    @private
    async def unlock_handle_attachments(self, dataset, options):
        for attachment_delegate in PoolDatasetService.attachment_delegates:
            # FIXME: put this into `VMFSAttachmentDelegate`
            if attachment_delegate.name == 'vm':
                await self.middleware.call('pool.dataset.restart_vms_after_unlock', dataset)
                continue

            attachments = await attachment_delegate.query(self.__attachments_path(dataset), True, {'locked': False})
            if attachments:
                await attachment_delegate.start(attachments)

    @accepts(
        Str('id'),
        Dict(
            'encryption_root_summary_options',
            Bool('key_file', default=False),
            Bool('force', default=False),
            List(
                'datasets', items=[
                    Dict(
                        'dataset',
                        Bool('force', required=True, default=False),
                        Str('name', required=True, empty=False),
                        Str('key', validators=[Range(min=64, max=64)], private=True),
                        Str('passphrase', empty=False, private=True),
                    )
                ],
            ),
        )
    )
    @returns(List(items=[Dict(
        'dataset_encryption_summary',
        Str('name', required=True),
        Str('key_format', required=True),
        Bool('key_present_in_database', required=True),
        Bool('valid_key', required=True),
        Bool('locked', required=True),
        Str('unlock_error', required=True, null=True),
        Bool('unlock_successful', required=True),
    )]))
    @job(lock=lambda args: f'encryption_summary_options_{args[0]}', pipes=['input'], check_pipes=False)
    def encryption_summary(self, job, id, options):
        """
        Retrieve summary of all encrypted roots under `id`.

        Keys/passphrase can be supplied to check if the keys are valid.

        It should be noted that there are 2 keys which show if a recursive unlock operation is
        done for `id`, which dataset will be unlocked and if not why it won't be unlocked. The keys
        namely are "unlock_successful" and "unlock_error". The former is a boolean value showing if unlock
        would succeed/fail. The latter is description why it failed if it failed.

        In some cases it's possible that the provided key/passphrase is valid but the path where the dataset is
        supposed to be mounted after being unlocked already exists and is not empty. In this case, unlock operation
        would fail and `unlock_error` will reflect this error appropriately. This can be overridden by setting
        `encryption_root_summary_options.datasets.X.force` boolean flag or by setting
        `encryption_root_summary_options.force` flag. In practice, when the dataset is going to be unlocked
        and these flags have been provided to `pool.dataset.unlock`, system will rename the directory/file path
        where the dataset should be mounted resulting in successful unlock of the dataset.

        If a dataset is already unlocked, it will show up as true for "unlock_successful" regardless of what
        key user provided as the unlock keys in the output are to reflect what a real unlock operation would
        behave. If user is interested in seeing if a provided key is valid or not, then the key to look out for
        in the output is "valid_key" which based on what system has in database or if a user provided one, validates
        the key and sets a boolean value for the dataset.

        Example output:
        [
            {
                "name": "vol",
                "key_format": "PASSPHRASE",
                "key_present_in_database": false,
                "valid_key": true,
                "locked": true,
                "unlock_error": null,
                "unlock_successful": true
            },
            {
                "name": "vol/c1/d1",
                "key_format": "PASSPHRASE",
                "key_present_in_database": false,
                "valid_key": false,
                "locked": true,
                "unlock_error": "Provided key is invalid",
                "unlock_successful": false
            },
            {
                "name": "vol/c",
                "key_format": "PASSPHRASE",
                "key_present_in_database": false,
                "valid_key": false,
                "locked": true,
                "unlock_error": "Key not provided",
                "unlock_successful": false
            },
            {
                "name": "vol/c/d2",
                "key_format": "PASSPHRASE",
                "key_present_in_database": false,
                "valid_key": false,
                "locked": true,
                "unlock_error": "Child cannot be unlocked when parent \"vol/c\" is locked and provided key is invalid",
                "unlock_successful": false
            }
        ]
        """
        keys_supplied = {}
        verrors = ValidationErrors()
        if options['key_file']:
            keys_supplied = {k: {'key': v, 'force': False} for k, v in self._retrieve_keys_from_file(job).items()}

        for i, ds in enumerate(options['datasets']):
            if all(ds.get(k) for k in ('key', 'passphrase')):
                verrors.add(
                    f'unlock_options.datasets.{i}.dataset.key',
                    f'Must not be specified when passphrase for {ds["name"]} is supplied'
                )
            keys_supplied[ds['name']] = {
                'key': ds.get('key') or ds.get('passphrase'),
                'force': ds['force'],
            }

        verrors.check()
        datasets = self.query_encrypted_datasets(id, {'all': True})

        to_check = []
        for name, ds in datasets.items():
            ds_key = keys_supplied.get(name, {}).get('key') or ds['encryption_key']
            if ZFSKeyFormat(ds['key_format']['value']) == ZFSKeyFormat.RAW and ds_key:
                with contextlib.suppress(ValueError):
                    ds_key = bytes.fromhex(ds_key)
            to_check.append((name, {'key': ds_key}))

        check_job = self.middleware.call_sync('zfs.dataset.bulk_process', 'check_key', to_check)
        check_job.wait_sync()
        if check_job.error:
            raise CallError(f'Failed to retrieve encryption summary for {id}: {check_job.error}')

        results = []
        for ds_data, status in zip(to_check, check_job.result):
            ds_name = ds_data[0]
            data = datasets[ds_name]
            results.append({
                'name': ds_name,
                'key_format': ZFSKeyFormat(data['key_format']['value']).value,
                'key_present_in_database': bool(data['encryption_key']),
                'valid_key': bool(status['result']), 'locked': data['locked'],
                'unlock_error': None,
                'unlock_successful': False,
            })

        failed = set()
        for ds in sorted(results, key=lambda d: d['name'].count('/')):
            for i in range(1, ds['name'].count('/') + 1):
                check = ds['name'].rsplit('/', i)[0]
                if check in failed:
                    failed.add(ds['name'])
                    ds['unlock_error'] = f'Child cannot be unlocked when parent "{check}" is locked'

            if ds['locked'] and not options['force'] and not keys_supplied.get(ds['name'], {}).get('force'):
                err = self.dataset_can_be_mounted(ds['name'], os.path.join('/mnt', ds['name']))
                if ds['unlock_error'] and err:
                    ds['unlock_error'] += f' and {err}'
                elif err:
                    ds['unlock_error'] = err

            if ds['valid_key']:
                ds['unlock_successful'] = not bool(ds['unlock_error'])
            elif not ds['locked']:
                # For datasets which are already not locked, unlock operation for them
                # will succeed as they are not locked
                ds['unlock_successful'] = True
            else:
                key_provided = ds['name'] in keys_supplied or ds['key_present_in_database']
                if key_provided:
                    if ds['unlock_error']:
                        if ds['name'] in keys_supplied or ds['key_present_in_database']:
                            ds['unlock_error'] += ' and provided key is invalid'
                    else:
                        ds['unlock_error'] = 'Provided key is invalid'
                elif not ds['unlock_error']:
                    ds['unlock_error'] = 'Key not provided'
                failed.add(ds['name'])

        return results

    @private
    def dataset_can_be_mounted(self, ds_name, ds_mountpoint):
        mount_error_check = ''
        if os.path.isfile(ds_mountpoint):
            mount_error_check = f'A file exists at {ds_mountpoint!r} and {ds_name} cannot be mounted'
        elif os.path.isdir(ds_mountpoint) and os.listdir(ds_mountpoint):
            mount_error_check = f'{ds_mountpoint!r} directory is not empty'
        mount_error_check += (
            ' (please provide "force" flag to override this error and file/directory '
            'will be renamed once the dataset is unlocked)' if mount_error_check else ''
        )
        return mount_error_check

    @accepts(
        Str('id'),
        Dict(
            'change_key_options',
            Bool('generate_key', default=False),
            Bool('key_file', default=False),
            Int('pbkdf2iters', default=350000, validators=[Range(min=100000)]),
            Str('passphrase', empty=False, default=None, null=True, private=True),
            Str('key', validators=[Range(min=64, max=64)], default=None, null=True, private=True),
        )
    )
    @returns()
    @job(lock=lambda args: f'dataset_change_key_{args[0]}', pipes=['input'], check_pipes=False)
    async def change_key(self, job, id, options):
        """
        Change encryption properties for `id` encrypted dataset.

        Changing dataset encryption to use passphrase instead of a key is not allowed if:

        1) It has encrypted roots as children which are encrypted with a key
        2) If it is a root dataset where the system dataset is located
        """
        ds = await self.get_instance(id)
        verrors = ValidationErrors()
        if not ds['encrypted']:
            verrors.add('id', 'Dataset is not encrypted')
        elif ds['locked']:
            verrors.add('id', 'Dataset must be unlocked before key can be changed')

        if not verrors:
            if options['passphrase']:
                if options['generate_key'] or options['key']:
                    verrors.add(
                        'change_key_options.key',
                        f'Must not be specified when passphrase for {id} is supplied.'
                    )
                elif any(
                    d['name'] == d['encryption_root']
                    for d in await self.middleware.run_in_thread(
                        self.query, [
                            ['id', '^', f'{id}/'], ['encrypted', '=', True],
                            ['key_format.value', '!=', ZFSKeyFormat.PASSPHRASE.value]
                        ]
                    )
                ):
                    verrors.add(
                        'change_key_options.passphrase',
                        f'{id} has children which are encrypted with a key. It is not allowed to have encrypted '
                        'roots which are encrypted with a key as children for passphrase encrypted datasets.'
                    )
                elif id == (await self.middleware.call('systemdataset.config'))['pool']:
                    verrors.add(
                        'id',
                        f'{id} contains the system dataset. Please move the system dataset to a '
                        'different pool before changing key_format.'
                    )
            else:
                if not options['generate_key'] and not options['key']:
                    for k in ('key', 'passphrase', 'generate_key'):
                        verrors.add(
                            f'change_key_options.{k}',
                            'Either Key or passphrase must be provided.'
                        )
                elif id.count('/') and await self.middleware.call(
                    'pool.dataset.query', [
                        ['id', 'in', [id.rsplit('/', i)[0] for i in range(1, id.count('/') + 1)]],
                        ['key_format.value', '=', ZFSKeyFormat.PASSPHRASE.value], ['encrypted', '=', True]
                    ]
                ):
                    verrors.add(
                        'change_key_options.key',
                        f'{id} has parent(s) which are encrypted with a passphrase. It is not allowed to have '
                        'encrypted roots which are encrypted with a key as children for passphrase encrypted datasets.'
                    )

        verrors.check()

        encryption_dict = await self.middleware.call(
            'pool.dataset.validate_encryption_data', job, verrors, {
                'enabled': True, 'passphrase': options['passphrase'],
                'generate_key': options['generate_key'], 'key_file': options['key_file'],
                'pbkdf2iters': options['pbkdf2iters'], 'algorithm': 'on', 'key': options['key'],
            }, 'change_key_options'
        )

        verrors.check()

        encryption_dict.pop('encryption')
        key = encryption_dict.pop('key')

        await self.middleware.call(
            'zfs.dataset.change_key', id, {
                'encryption_properties': encryption_dict,
                'key': key, 'load_key': False,
            }
        )

        # TODO: Handle renames of datasets appropriately wrt encryption roots and db - this will be done when
        #  devd changes are in from the OS end
        data = {'encryption_key': key, 'key_format': 'PASSPHRASE' if options['passphrase'] else 'HEX', 'name': id}
        await self.insert_or_update_encrypted_record(data)
        if options['passphrase'] and ZFSKeyFormat(ds['key_format']['value']) != ZFSKeyFormat.PASSPHRASE:
            await self.middleware.call('pool.dataset.sync_db_keys', id)

        data['old_key_format'] = ds['key_format']['value']
        await self.middleware.call_hook('dataset.change_key', data)

    @accepts(Str('id'))
    @returns()
    async def inherit_parent_encryption_properties(self, id):
        """
        Allows inheriting parent's encryption root discarding its current encryption settings. This
        can only be done where `id` has an encrypted parent and `id` itself is an encryption root.
        """
        ds = await self.get_instance(id)
        if not ds['encrypted']:
            raise CallError(f'Dataset {id} is not encrypted')
        elif ds['encryption_root'] != id:
            raise CallError(f'Dataset {id} is not an encryption root')
        elif ds['locked']:
            raise CallError('Dataset must be unlocked to perform this operation')
        elif '/' not in id:
            raise CallError('Root datasets do not have a parent and cannot inherit encryption settings')
        else:
            parent = await self.get_instance(id.rsplit('/', 1)[0])
            if not parent['encrypted']:
                raise CallError('This operation requires the parent dataset to be encrypted')
            else:
                parent_encrypted_root = await self.get_instance(parent['encryption_root'])
                if ZFSKeyFormat(parent_encrypted_root['key_format']['value']) == ZFSKeyFormat.PASSPHRASE.value:
                    if any(
                        d['name'] == d['encryption_root']
                        for d in await self.middleware.run_in_thread(
                            self.query, [
                                ['id', '^', f'{id}/'], ['encrypted', '=', True],
                                ['key_format.value', '!=', ZFSKeyFormat.PASSPHRASE.value]
                            ]
                        )
                    ):
                        raise CallError(
                            f'{id} has children which are encrypted with a key. It is not allowed to have encrypted '
                            'roots which are encrypted with a key as children for passphrase encrypted datasets.'
                        )

        await self.middleware.call('zfs.dataset.change_encryption_root', id, {'load_key': False})
        await self.middleware.call('pool.dataset.sync_db_keys', id)
        await self.middleware.call_hook('dataset.inherit_parent_encryption_root', id)

    @private
    def _retrieve_keys_from_file(self, job):
        job.check_pipe('input')
        try:
            data = json.loads(job.pipes.input.r.read(10 * MB))
        except json.JSONDecodeError:
            raise CallError('Input file must be a valid JSON file')

        if not isinstance(data, dict) or any(not isinstance(v, str) for v in data.values()):
            raise CallError('Please specify correct format for input file')

        return data

    @private
    async def internal_datasets_filters(self):
        # We get filters here which ensure that we don't match an internal dataset
        filters = []
        try:
            sysds = (await self.middleware.call('cache.get', 'SYSDATASET_PATH'))['dataset']
        except KeyError:
            sysds = (await self.middleware.call('systemdataset.config'))['basename']

        if sysds:
            filters.extend([['id', '!=', sysds], ['id', '!^', f'{sysds}/']])

        filters.append(['pool', '!=', await self.middleware.call('boot.pool_name')])

        # top level dataset that stores all things related to gluster config
        # needs to be hidden from local webUI. (This is managed by TrueCommander)
        filters.extend([
            ['id', 'rnin', '.glusterfs'],
            ['id', 'rnin', '/ix-applications/'],
        ])

        return filters

    @private
    async def is_internal_dataset(self, dataset):
        return not bool(filter_list([{'id': dataset}], await self.internal_datasets_filters()))

    @private
    def path_in_locked_datasets(self, path, locked_datasets=None):
        if locked_datasets is None:
            locked_datasets = self.middleware.call_sync('zfs.dataset.locked_datasets')
        return any(is_child(path, d['mountpoint']) for d in locked_datasets if d['mountpoint'])

    @filterable
    def query(self, filters, options):
        """
        Query Pool Datasets with `query-filters` and `query-options`.

        We provide two ways to retrieve datasets. The first is a flat structure (default), where
        all datasets in the system are returned as separate objects which contain all data
        there is for their children. This retrieval type is slightly slower because of duplicates in each object.
        The second type is hierarchical, where only top level datasets are returned in the list. They contain all the
        children in the `children` key. This retrieval type is slightly faster.
        These options are controlled by the `query-options.extra.flat` attribute (default true).

        In some cases it might be desirable to only retrieve details of a dataset itself and not it's children, in this
        case `query-options.extra.retrieve_children` should be explicitly specified and set to `false` which will
        result in children not being retrieved.

        In case only some properties are desired to be retrieved for datasets, consumer should specify
        `query-options.extra.properties` which when `null` ( which is the default ) will retrieve all properties
        and otherwise a list can be specified like `["type", "used", "available"]` to retrieve selective properties.
        If no properties are desired, in that case an empty list should be sent.

        `query-options.extra.snapshots` can be set to retrieve snapshot(s) of dataset in question.

        `query-options.extra.snapshots_recursive` can be set to retrieve snapshot(s) recursively of dataset in question.
        If `query-options.extra.snapshots_recursive` and `query-options.extra.snapshots` are set, snapshot(s) will be
        retrieved recursively.

        `query-options.extra.snapshots_properties` can be specified to list out properties which should be retrieved
        for snapshot(s) related to each dataset. By default only name of the snapshot would be retrieved, however
        if `null` is specified all properties of the snapshot would be retrieved in this case.
        """
        # Optimization for cases in which they can be filtered at zfs.dataset.query
        zfsfilters = []
        filters = filters or []
        if len(filters) == 1 and len(filters[0]) == 3 and list(filters[0][:2]) == ['id', '=']:
            zfsfilters.append(copy.deepcopy(filters[0]))

        internal_datasets_filters = self.middleware.call_sync('pool.dataset.internal_datasets_filters')
        filters.extend(internal_datasets_filters)
        extra = copy.deepcopy(options.get('extra', {}))
        retrieve_children = extra.get('retrieve_children', True)
        props = extra.get('properties')
        snapshots = extra.get('snapshots')
        snapshots_recursive = extra.get('snapshots_recursive')
        return filter_list(
            self.__transform(self.middleware.call_sync(
                'zfs.dataset.query', zfsfilters, {
                    'extra': {
                        'flat': extra.get('flat', True),
                        'retrieve_children': retrieve_children,
                        'properties': props,
                        'snapshots': snapshots,
                        'snapshots_recursive': snapshots_recursive,
                        'snapshots_properties': extra.get('snapshots_properties', [])
                    }
                }
            ), retrieve_children, internal_datasets_filters,
            ), filters, options
        )

    def _internal_user_props(self):
        return [
            'org.freenas:description',
            'org.freenas:quota_warning',
            'org.freenas:quota_critical',
            'org.freenas:refquota_warning',
            'org.freenas:refquota_critical',
            'org.truenas:managedby',
        ]

    def __transform(self, datasets, retrieve_children, children_filters):
        """
        We need to transform the data zfs gives us to make it consistent/user-friendly,
        making it match whatever pool.dataset.{create,update} uses as input.
        """

        def transform(dataset):
            for orig_name, new_name, method in get_props_of_interest_mapping():
                if orig_name not in dataset['properties']:
                    continue
                i = new_name or orig_name
                dataset[i] = dataset['properties'][orig_name]
                if method:
                    dataset[i]['value'] = method(dataset[i]['value'])

            if 'mountpoint' in dataset:
                # This is treated specially to keep backwards compatibility with API
                dataset['mountpoint'] = dataset['mountpoint']['value']
            if dataset['type'] == 'VOLUME':
                dataset['mountpoint'] = None

            dataset['user_properties'] = {
                k: v for k, v in dataset['properties'].items() if ':' in k and k not in self._internal_user_props()
            }
            del dataset['properties']

            if all(k in dataset for k in ('encrypted', 'key_loaded')):
                dataset['locked'] = dataset['encrypted'] and not dataset['key_loaded']

            if retrieve_children:
                rv = []
                for child in filter_list(dataset['children'], children_filters):
                    rv.append(transform(child))
                dataset['children'] = rv

            return dataset

        rv = []
        for dataset in datasets:
            rv.append(transform(dataset))
        return rv

    @accepts(Dict(
        'pool_dataset_create',
        Str('name', required=True),
        Str('type', enum=['FILESYSTEM', 'VOLUME'], default='FILESYSTEM'),
        Int('volsize'),  # IN BYTES
        Str('volblocksize', enum=[
            '512', '512B', '1K', '2K', '4K', '8K', '16K', '32K', '64K', '128K',
        ]),
        Bool('sparse'),
        Bool('force_size'),
        Inheritable(Str('comments')),
        Inheritable(Str('sync', enum=['STANDARD', 'ALWAYS', 'DISABLED'])),
        Inheritable(Str('snapdev', enum=['HIDDEN', 'VISIBLE']), has_default=False),
        Inheritable(Str('compression', enum=ZFS_COMPRESSION_ALGORITHM_CHOICES)),
        Inheritable(Str('atime', enum=['ON', 'OFF']), has_default=False),
        Inheritable(Str('exec', enum=['ON', 'OFF'])),
        Inheritable(Str('managedby', empty=False)),
        Int('quota', null=True, validators=[Or(Range(min=1024**3), Exact(0))]),
        Inheritable(Int('quota_warning', validators=[Range(0, 100)])),
        Inheritable(Int('quota_critical', validators=[Range(0, 100)])),
        Int('refquota', null=True, validators=[Or(Range(min=1024**3), Exact(0))]),
        Inheritable(Int('refquota_warning', validators=[Range(0, 100)])),
        Inheritable(Int('refquota_critical', validators=[Range(0, 100)])),
        Int('reservation'),
        Int('refreservation'),
        Inheritable(Int('special_small_block_size'), has_default=False),
        Inheritable(Int('copies')),
        Inheritable(Str('snapdir', enum=['VISIBLE', 'HIDDEN'])),
        Inheritable(Str('deduplication', enum=['ON', 'VERIFY', 'OFF'])),
        Inheritable(Str('checksum', enum=ZFS_CHECKSUM_CHOICES)),
        Inheritable(Str('readonly', enum=['ON', 'OFF'])),
        Inheritable(Str('recordsize'), has_default=False),
        Inheritable(Str('casesensitivity', enum=['SENSITIVE', 'INSENSITIVE', 'MIXED']), has_default=False),
        Inheritable(Str('aclmode', enum=['PASSTHROUGH', 'RESTRICTED', 'DISCARD']), has_default=False),
        Inheritable(Str('acltype', enum=['OFF', 'NFSV4', 'POSIX']), has_default=False),
        Str('share_type', default='GENERIC', enum=['GENERIC', 'SMB']),
        Inheritable(Str('xattr', default='SA', enum=['ON', 'SA'])),
        Ref('encryption_options'),
        Bool('encryption', default=False),
        Bool('inherit_encryption', default=True),
        List(
            'user_properties',
            items=[Dict(
                'user_property',
                Str('key', required=True, validators=[Match(r'.*:.*')]),
                Str('value', required=True),
            )],
        ),
        Bool('create_ancestors', default=False),
        register=True,
    ))
    @pass_app(rest=True)
    async def do_create(self, app, data):
        """
        Creates a dataset/zvol.

        `volsize` is required for type=VOLUME and is supposed to be a multiple of the block size.
        `sparse` and `volblocksize` are only used for type=VOLUME.

        `encryption` when enabled will create an ZFS encrypted root dataset for `name` pool.
        There are 2 cases where ZFS encryption is not allowed for a dataset:
        1) Pool in question is GELI encrypted.
        2) If the parent dataset is encrypted with a passphrase and `name` is being created
           with a key for encrypting the dataset.

        `encryption_options` specifies configuration for encryption of dataset for `name` pool.
        `encryption_options.passphrase` must be specified if encryption for dataset is desired with a passphrase
        as a key.
        Otherwise a hex encoded key can be specified by providing `encryption_options.key`.
        `encryption_options.generate_key` when enabled automatically generates the key to be used
        for dataset encryption.

        It should be noted that keys are stored by the system for automatic locking/unlocking
        on import/export of encrypted datasets. If that is not desired, dataset should be created
        with a passphrase as a key.

        .. examples(websocket)::

          Create a dataset within tank pool.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.dataset.create,
                "params": [{
                    "name": "tank/myuser",
                    "comments": "Dataset for myuser"
                }]
            }
        """
        verrors = ValidationErrors()

        if '/' not in data['name']:
            verrors.add('pool_dataset_create.name', 'You need a full name, e.g. pool/newdataset')
        elif not validate_dataset_name(data['name']):
            verrors.add('pool_dataset_create.name', 'Invalid dataset name')
        elif len(data['name']) > ZFS_MAX_DATASET_NAME_LEN:
            verrors.add(
                'pool_dataset_create.name',
                f'Dataset name length should be less than or equal to {ZFS_MAX_DATASET_NAME_LEN}',
            )
        elif data['name'][-1] == ' ':
            verrors.add(
                'pool_dataset_create.name',
                'Trailing spaces are not permitted in dataset names'
            )
        else:
            parent_name = data['name'].rsplit('/', 1)[0]
            if data['create_ancestors']:
                # If we want to create ancestors, let's just ensure that we have at least one parent which exists
                while not await self.middleware.call(
                    'pool.dataset.query',
                    [['id', '=', parent_name]], {
                        'extra': {'retrieve_children': False, 'properties': []}
                    }
                ):
                    if '/' not in parent_name:
                        # Root dataset / pool does not exist
                        break
                    parent_name = parent_name.rsplit('/', 1)[0]

            parent_ds = await self.middleware.call(
                'pool.dataset.query',
                [('id', '=', parent_name)],
                {'extra': {'retrieve_children': False}}
            )
            await self.__common_validation(verrors, 'pool_dataset_create', data, 'CREATE', parent_ds)

        verrors.check()

        parent_ds = parent_ds[0]
        mountpoint = os.path.join('/mnt', data['name'])
        if data['type'] == 'FILESYSTEM' and data.get('acltype', 'INHERIT') == 'INHERIT' and len(
            data['name'].split('/')
        ) == 2:
            data['acltype'] = 'POSIX'

        if os.path.exists(mountpoint):
            verrors.add('pool_dataset_create.name', f'Path {mountpoint} already exists')

        if data['share_type'] == 'SMB':
            data['casesensitivity'] = 'INSENSITIVE'
            data['acltype'] = 'NFSV4'
            data['aclmode'] = 'RESTRICTED'

        if data['type'] == 'FILESYSTEM' and data.get('acltype', 'INHERIT') != 'INHERIT':
            data['aclinherit'] = 'PASSTHROUGH' if data['acltype'] == 'NFSV4' else 'DISCARD'

        if parent_ds['locked']:
            verrors.add(
                'pool_dataset_create.name',
                f'{data["name"].rsplit("/", 1)[0]} must be unlocked to create {data["name"]}.'
            )

        encryption_dict = {}
        inherit_encryption_properties = data.pop('inherit_encryption')
        if not inherit_encryption_properties:
            encryption_dict = {'encryption': 'off'}

        if data['encryption']:
            if inherit_encryption_properties:
                verrors.add('pool_dataset_create.inherit_encryption', 'Must be disabled when encryption is enabled.')
            if (
                await self.middleware.call('pool.query', [['name', '=', data['name'].split('/')[0]]], {'get': True})
            )['encrypt']:
                verrors.add(
                    'pool_dataset_create.encryption',
                    'Encrypted datasets cannot be created on a GELI encrypted pool.'
                )

            if not data['encryption_options']['passphrase']:
                # We want to ensure that we don't have any parent for this dataset which is encrypted with PASSPHRASE
                # because we don't allow children to be unlocked while parent is locked
                parent_encryption_root = parent_ds['encryption_root']
                if (
                    parent_encryption_root and ZFSKeyFormat(
                        (await self.get_instance(parent_encryption_root))['key_format']['value']
                    ) == ZFSKeyFormat.PASSPHRASE
                ):
                    verrors.add(
                        'pool_dataset_create.encryption',
                        'Passphrase encrypted datasets cannot have children encrypted with a key.'
                    )

        encryption_dict = await self.middleware.call(
            'pool.dataset.validate_encryption_data', None, verrors,
            {'enabled': data.pop('encryption'), **data.pop('encryption_options'), 'key_file': False},
            'pool_dataset_create.encryption_options',
        ) or encryption_dict
        verrors.check()

        if app:
            uri = None
            if app.rest and app.host:
                uri = app.host
            elif app.websocket and app.request.headers.get('X-Real-Remote-Addr'):
                uri = app.request.headers.get('X-Real-Remote-Addr')
            if uri and uri not in [
                '::1', '127.0.0.1', *[d['address'] for d in await self.middleware.call('interface.ip_in_use')]
            ]:
                data['managedby'] = uri if not data['managedby'] != 'INHERIT' else f'{data["managedby"]}@{uri}'

        props = {}
        for i, real_name, transform, inheritable in (
            ('aclinherit', None, str.lower, True),
            ('aclmode', None, str.lower, True),
            ('acltype', None, str.lower, True),
            ('atime', None, str.lower, True),
            ('casesensitivity', None, str.lower, True),
            ('checksum', None, str.lower, True),
            ('comments', 'org.freenas:description', None, True),
            ('compression', None, str.lower, True),
            ('copies', None, str, True),
            ('deduplication', 'dedup', str.lower, True),
            ('exec', None, str.lower, True),
            ('managedby', 'org.truenas:managedby', None, True),
            ('quota', None, _none, True),
            ('quota_warning', 'org.freenas:quota_warning', str, True),
            ('quota_critical', 'org.freenas:quota_critical', str, True),
            ('readonly', None, str.lower, True),
            ('recordsize', None, None, True),
            ('refquota', None, _none, True),
            ('refquota_warning', 'org.freenas:refquota_warning', str, True),
            ('refquota_critical', 'org.freenas:refquota_critical', str, True),
            ('refreservation', None, _none, False),
            ('reservation', None, _none, False),
            ('snapdir', None, str.lower, True),
            ('snapdev', None, str.lower, True),
            ('sparse', None, None, False),
            ('sync', None, str.lower, True),
            ('volblocksize', None, None, False),
            ('volsize', None, lambda x: str(x), False),
            ('xattr', None, str.lower, True),
            ('special_small_block_size', 'special_small_blocks', None, True),
        ):
            if i not in data or (inheritable and data[i] == 'INHERIT'):
                continue
            name = real_name or i
            props[name] = data[i] if not transform else transform(data[i])

        props.update(
            **encryption_dict,
            **(await self.get_create_update_user_props(data['user_properties']))
        )

        await self.middleware.call('zfs.dataset.create', {
            'name': data['name'],
            'type': data['type'],
            'properties': props,
            'create_ancestors': data['create_ancestors'],
        })

        dataset_data = {
            'name': data['name'], 'encryption_key': encryption_dict.get('key'),
            'key_format': encryption_dict.get('keyformat')
        }
        await self.insert_or_update_encrypted_record(dataset_data)
        await self.middleware.call_hook('dataset.post_create', {'encrypted': bool(encryption_dict), **dataset_data})

        data['id'] = data['name']

        await self.middleware.call('zfs.dataset.mount', data['name'])

        created_ds = await self.get_instance(data['id'])

        if data['type'] == 'FILESYSTEM' and data['share_type'] == 'SMB' and created_ds['acltype']['value'] == "NFSV4":
            acl_job = await self.middleware.call(
                'pool.dataset.permission', data['id'], {'options': {'set_default_acl': True}}
            )
            await acl_job.wait()

        return created_ds

    @private
    async def get_create_update_user_props(self, user_properties, update=False):
        props = {}
        for prop in user_properties:
            if 'value' in prop:
                props[prop['key']] = {'value': prop['value']} if update else prop['value']
            elif prop.get('remove'):
                props[prop['key']] = {'source': 'INHERIT'}
        return props

    @accepts(Str('id', required=True), Patch(
        'pool_dataset_create', 'pool_dataset_update',
        ('rm', {'name': 'name'}),
        ('rm', {'name': 'type'}),
        ('rm', {'name': 'casesensitivity'}),  # Its a readonly attribute
        ('rm', {'name': 'share_type'}),  # This is something we should only do at create time
        ('rm', {'name': 'sparse'}),  # Create time only attribute
        ('rm', {'name': 'volblocksize'}),  # Create time only attribute
        ('rm', {'name': 'encryption'}),  # Create time only attribute
        ('rm', {'name': 'encryption_options'}),  # Create time only attribute
        ('rm', {'name': 'inherit_encryption'}),  # Create time only attribute
        ('add', List(
            'user_properties_update',
            items=[Dict(
                'user_property',
                Str('key', required=True, validators=[Match(r'.*:.*')]),
                Str('value'),
                Bool('remove'),
            )],
        )),
        ('attr', {'update': True}),
    ))
    async def do_update(self, id, data):
        """
        Updates a dataset/zvol `id`.

        .. examples(websocket)::

          Update the `comments` for "tank/myuser".

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.dataset.update,
                "params": ["tank/myuser", {
                    "comments": "Dataset for myuser, UPDATE #1"
                }]
            }
        """
        verrors = ValidationErrors()

        dataset = await self.middleware.call(
            'pool.dataset.query', [('id', '=', id)], {'extra': {'retrieve_children': False}}
        )
        if not dataset:
            verrors.add('id', f'{id} does not exist', errno.ENOENT)
        else:
            data['type'] = dataset[0]['type']
            data['name'] = dataset[0]['name']
            if data['type'] == 'VOLUME':
                data['volblocksize'] = dataset[0]['volblocksize']['value']
            await self.__common_validation(verrors, 'pool_dataset_update', data, 'UPDATE', cur_dataset=dataset[0])
            if 'volsize' in data:
                if data['volsize'] < dataset[0]['volsize']['parsed']:
                    verrors.add('pool_dataset_update.volsize',
                                'You cannot shrink a zvol from GUI, this may lead to data loss.')
            if dataset[0]['type'] == 'VOLUME':
                existing_snapdev_prop = dataset[0]['snapdev']['parsed'].upper()
                snapdev_prop = data.get('snapdev') or existing_snapdev_prop
                if existing_snapdev_prop != snapdev_prop and snapdev_prop in ('INHERIT', 'HIDDEN'):
                    if await self.middleware.call(
                        'zfs.dataset.unlocked_zvols_fast',
                        [['attachment', '!=', None], ['ro', '=', True], ['name', '^', f'{id}@']],
                        {}, ['RO', 'ATTACHMENT']
                    ):
                        verrors.add(
                            'pool_dataset_update.snapdev',
                            f'{id!r} has snapshots which have attachments being used. Before marking it '
                            'as HIDDEN, remove attachment usages.'
                        )

        verrors.check()

        properties_definitions = (
            ('aclinherit', None, str.lower, True),
            ('aclmode', None, str.lower, True),
            ('acltype', None, str.lower, True),
            ('atime', None, str.lower, True),
            ('checksum', None, str.lower, True),
            ('comments', 'org.freenas:description', None, False),
            ('sync', None, str.lower, True),
            ('compression', None, str.lower, True),
            ('deduplication', 'dedup', str.lower, True),
            ('exec', None, str.lower, True),
            ('managedby', 'org.truenas:managedby', None, True),
            ('quota', None, _none, False),
            ('quota_warning', 'org.freenas:quota_warning', str, True),
            ('quota_critical', 'org.freenas:quota_critical', str, True),
            ('refquota', None, _none, False),
            ('refquota_warning', 'org.freenas:refquota_warning', str, True),
            ('refquota_critical', 'org.freenas:refquota_critical', str, True),
            ('reservation', None, _none, False),
            ('refreservation', None, _none, False),
            ('copies', None, str, True),
            ('snapdir', None, str.lower, True),
            ('snapdev', None, str.lower, True),
            ('readonly', None, str.lower, True),
            ('recordsize', None, None, True),
            ('volsize', None, lambda x: str(x), False),
            ('special_small_block_size', 'special_small_blocks', None, True),
        )

        props = {}
        for i, real_name, transform, inheritable in properties_definitions:
            if i not in data:
                continue
            name = real_name or i
            if inheritable and data[i] == 'INHERIT':
                props[name] = {'source': 'INHERIT'}
            else:
                props[name] = {'value': data[i] if not transform else transform(data[i])}

        if data.get('user_properties_update'):
            props.update(await self.get_create_update_user_props(data['user_properties_update'], True))

        if 'acltype' in props and (acltype_value := props['acltype'].get('value')):
            if acltype_value == 'nfsv4':
                props.update({
                    'aclinherit': {'value': 'passthrough'}
                })
            elif acltype_value in ['posix', 'off']:
                props.update({
                    'aclmode': {'value': 'discard'},
                    'aclinherit': {'value': 'discard'}
                })
            elif props['acltype'].get('source') == 'INHERIT':
                props.update({
                    'aclmode': {'source': 'INHERIT'},
                    'aclinherit': {'source': 'INHERIT'}
                })

        try:
            await self.middleware.call('zfs.dataset.update', id, {'properties': props})
        except ZFSSetPropertyError as e:
            verrors = ValidationErrors()
            verrors.add_child('pool_dataset_update', self.__handle_zfs_set_property_error(e, properties_definitions))
            raise verrors

        if data['type'] == 'VOLUME' and 'volsize' in data and data['volsize'] > dataset[0]['volsize']['parsed']:
            # means the zvol size has increased so we need to check if this zvol is shared via SCST (iscs)
            # and if it is, resync it so the connected initiators can see the new size of the zvol
            await self.middleware.call('iscsi.global.resync_lun_size_for_zvol', id)

        return await self.get_instance(id)

    async def __common_validation(self, verrors, schema, data, mode, parent=None, cur_dataset=None):
        assert mode in ('CREATE', 'UPDATE')

        if parent is None:
            parent = await self.middleware.call(
                'pool.dataset.query',
                [('id', '=', data['name'].rsplit('/', 1)[0])],
                {'extra': {'retrieve_children': False}}
            )

        if await self.is_internal_dataset(data['name']):
            verrors.add(
                f'{schema}.name',
                f'{data["name"]!r} is using system internal managed dataset. Please specify a different parent.'
            )

        if not parent:
            # This will only be true on dataset creation
            if data['create_ancestors']:
                verrors.add(
                    f'{schema}.name',
                    'Please specify a pool which exists for the dataset/volume to be created'
                )
            else:
                verrors.add(f'{schema}.name', 'Parent dataset does not exist for specified name')
        else:
            parent = parent[0]
            if mode == 'CREATE' and parent['readonly']['rawvalue'] == 'on':
                # creating a zvol/dataset when the parent object is set to readonly=on
                # is allowed via ZFS. However, if it's a dataset an error will be raised
                # stating that it was unable to be mounted. If it's a zvol, then the service
                # that tries to open the zvol device will get read only related errors.
                # Currently, there is no way to mount a dataset in the webUI so we will
                # prevent this scenario from occuring by preventing creation if the parent
                # is set to readonly=on.
                verrors.add(
                    f'{schema}.readonly',
                    f'Turn off readonly mode on {parent["id"]} to create {data["name"].rsplit("/")[0]}'
                )

        # We raise validation errors here as parent could be used down to validate other aspects of the dataset
        verrors.check()

        if data['type'] == 'FILESYSTEM':
            if data.get('acltype', 'INHERIT') != 'INHERIT' or data.get('aclmode', 'INHERIT') != 'INHERIT':
                to_check = data.copy()
                check_ds = cur_dataset if mode == 'UPDATE' else parent
                if data.get('aclmode', 'INHERIT') == 'INHERIT':
                    to_check['aclmode'] = check_ds['aclmode']['value']

                if data.get('acltype', 'INHERIT') == 'INHERIT':
                    to_check['acltype'] = check_ds['acltype']['value']

                acltype = to_check.get('acltype', 'POSIX')
                if acltype in ['POSIX', 'OFF'] and to_check.get('aclmode', 'DISCARD') != 'DISCARD':
                    verrors.add(f'{schema}.aclmode', 'Must be set to DISCARD when acltype is POSIX or OFF')

            for i in ('force_size', 'sparse', 'volsize', 'volblocksize'):
                if i in data:
                    verrors.add(f'{schema}.{i}', 'This field is not valid for FILESYSTEM')

            if (c_value := data.get('special_small_block_size')) is not None:
                if c_value != 'INHERIT' and not (
                    (c_value == 0 or 512 <= c_value <= 1048576) and ((c_value & (c_value - 1)) == 0)
                ):
                    verrors.add(
                        f'{schema}.special_small_block_size',
                        'This field must be zero or a power of 2 from 512B to 1M'
                    )

            if rs := data.get('recordsize'):
                if rs != 'INHERIT' and rs not in await self.middleware.call('pool.dataset.recordsize_choices'):
                    verrors.add(f'{schema}.recordsize', f'{rs!r} is an invalid recordsize.')

        elif data['type'] == 'VOLUME':
            if mode == 'CREATE' and 'volsize' not in data:
                verrors.add(f'{schema}.volsize', 'This field is required for VOLUME')

            for i in (
                'aclmode', 'acltype', 'atime', 'casesensitivity', 'quota', 'refquota', 'recordsize',
            ):
                if i in data:
                    verrors.add(f'{schema}.{i}', 'This field is not valid for VOLUME')

            if 'volsize' in data and parent:

                avail_mem = int(parent['available']['rawvalue'])

                if mode == 'UPDATE':
                    avail_mem += int((await self.get_instance(data['name']))['used']['rawvalue'])

                if (
                    data['volsize'] > (avail_mem * 0.80) and
                    not data.get('force_size', False)
                ):
                    verrors.add(
                        f'{schema}.volsize',
                        'It is not recommended to use more than 80% of your available space for VOLUME'
                    )

                if 'volblocksize' in data:

                    if data['volblocksize'][:3] == '512':
                        block_size = 512
                    else:
                        block_size = int(data['volblocksize'][:-1]) * 1024

                    if data['volsize'] % block_size:
                        verrors.add(
                            f'{schema}.volsize',
                            'Volume size should be a multiple of volume block size'
                        )

        if mode == 'UPDATE':
            if data.get('user_properties_update') and not data.get('user_properties'):
                for index, prop in enumerate(data['user_properties_update']):
                    prop_schema = f'{schema}.user_properties_update.{index}'
                    if 'value' in prop and prop.get('remove'):
                        verrors.add(f'{prop_schema}.remove', 'When "value" is specified, this cannot be set')
                    elif not any(k in prop for k in ('value', 'remove')):
                        verrors.add(f'{prop_schema}.value', 'Either "value" or "remove" must be specified')
            elif data.get('user_properties') and data.get('user_properties_update'):
                verrors.add(
                    f'{schema}.user_properties_update',
                    'Should not be specified when "user_properties" are explicitly specified'
                )
            elif data.get('user_properties'):
                # Let's normalize this so that we create/update/remove user props accordingly
                user_props = {p['key'] for p in data['user_properties']}
                data['user_properties_update'] = data['user_properties']
                for prop_key in [k for k in cur_dataset['user_properties'] if k not in user_props]:
                    data['user_properties_update'].append({
                        'key': prop_key,
                        'remove': True,
                    })

    def __handle_zfs_set_property_error(self, e, properties_definitions):
        zfs_name_to_api_name = {i[1]: i[0] for i in properties_definitions}
        api_name = zfs_name_to_api_name.get(e.property) or e.property
        verrors = ValidationErrors()
        verrors.add(api_name, e.error)
        return verrors

    @accepts(Str('id'), Dict(
        'dataset_delete',
        Bool('recursive', default=False),
        Bool('force', default=False),
    ))
    async def do_delete(self, id, options):
        """
        Delete dataset/zvol `id`.

        `recursive` will also delete/destroy all children datasets.
        `force` will force delete busy datasets.

        .. examples(websocket)::

          Delete "tank/myuser" dataset.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.dataset.delete",
                "params": ["tank/myuser"]
            }
        """

        if not options['recursive'] and await self.middleware.call('zfs.dataset.query', [['id', '^', f'{id}/']]):
            raise CallError(f'Failed to delete dataset: cannot destroy {id!r}: filesystem has children',
                            errno.ENOTEMPTY)

        dataset = await self.get_instance(id)
        path = self.__attachments_path(dataset)
        if path:
            for delegate in self.attachment_delegates:
                attachments = await delegate.query(path, True)
                if attachments:
                    await delegate.delete(attachments)

        if dataset['locked'] and dataset['mountpoint'] and os.path.exists(dataset['mountpoint']):
            # We would like to remove the immutable flag in this case so that it's mountpoint can be
            # cleaned automatically when we delete the dataset
            await self.middleware.call('filesystem.set_immutable', False, dataset['mountpoint'])

        result = await self.middleware.call('zfs.dataset.delete', id, {
            'force': options['force'],
            'recursive': options['recursive'],
        })
        return result

    @accepts(
        Str('name'),
        Dict(
            'snapshots',
            Bool('all', default=True),
            Bool('recursive', default=False),
            List(
                'snapshots', items=[Dict(
                    'snapshot_spec',
                    Str('start'),
                    Str('end'),
                ), Str('snapshot_name')]
            ),
        ),
    )
    @returns(List('deleted_snapshots', items=[Str('deleted_snapshot')]))
    @job(lock=lambda args: f'destroy_snapshots_{args[0]}')
    async def destroy_snapshots(self, job, name, snapshots_spec):
        """
        Destroy specified snapshots of a given dataset.
        """
        await self.get_instance(name, {'extra': {
            'properties': [],
            'retrieve_children': False,
        }})

        verrors = ValidationErrors()
        schema_name = 'destroy_snapshots'
        if snapshots_spec['all'] and snapshots_spec['snapshots']:
            verrors.add(
                f'{schema_name}.snapshots', 'Must not be specified when all snapshots are specified for removal'
            )
        else:
            for i, entry in enumerate(snapshots_spec['snapshots']):
                if not entry:
                    verrors.add(f'{schema_name}.snapshots.{i}', 'Either "start" or "end" must be specified')

        verrors.check()

        job.set_progress(20, 'Initial validation complete')

        return await self.middleware.call('zfs.dataset.destroy_snapshots', name, snapshots_spec)

    @item_method
    @accepts(Str('id'))
    @returns()
    async def promote(self, id):
        """
        Promote the cloned dataset `id`.
        """
        dataset = await self.middleware.call('zfs.dataset.query', [('id', '=', id)])
        if not dataset:
            raise CallError(f'Dataset "{id}" does not exist.', errno.ENOENT)
        if not dataset[0]['properties']['origin']['value']:
            raise CallError('Only cloned datasets can be promoted.', errno.EBADMSG)
        return await self.middleware.call('zfs.dataset.promote', id)

    @private
    async def from_path(self, path, check_parents):
        p = Path(path)
        if not p.is_absolute():
            raise CallError(f"[{path}] is not an absolute path.", errno.EINVAL)

        if not p.exists() and check_parents:
            for parent in p.parents:
                if parent.exists():
                    p = parent
                    break

        ds_name = await self.middleware.call("zfs.dataset.path_to_dataset", p.as_posix(), True)
        return await self.middleware.call(
            "pool.dataset.query",
            [("id", "=", ds_name)],
            {"get": True}
        )

    @accepts(
        Str('id', required=True),
        Dict(
            'pool_dataset_permission',
            Str('user'),
            Str('group'),
            UnixPerm('mode', null=True),
            OROperator(
                Ref('nfs4_acl'),
                Ref('posix1e_acl'),
                name='acl'
            ),
            Dict(
                'options',
                Bool('set_default_acl', default=False),
                Bool('stripacl', default=False),
                Bool('recursive', default=False),
                Bool('traverse', default=False),
            ),
            register=True,
        ),
    )
    @returns(Ref('pool_dataset_permission'))
    @item_method
    @job(lock="dataset_permission_change")
    async def permission(self, job, id, data):
        """
        Set permissions for a dataset `id`. Permissions may be specified as
        either a posix `mode` or an `acl`. This method is a wrapper around
        `filesystem.setperm`, `filesystem.setacl`, and `filesystem.chown`

        `filesystem.setperm` is called if `mode` is specified.
        `filesystem.setacl` is called if `acl` is specified or if the
        option `set_default_acl` is selected.
        `filesystem.chown` is called if neither `mode` nor `acl` is
        specified.

        The following `options` are supported:

        `set_default_acl` - apply a default ACL appropriate for specified
        dataset. Default ACL is `NFS4_RESTRICTED` or `POSIX_RESTRICTED`
        ACL template builtin with additional entries builtin_users group
        and builtin_administrators group. See documentation for
        `filesystem.acltemplate` for more details.

        `stripacl` - this option must be set in order to apply a POSIX
        mode to a dataset that has a non-trivial ACL. The effect will
        be to remove existing ACL and replace with specified mode.

        `recursive` - apply permissions recursively to dataset (all files
        and directories will be impacted.

        `traverse` - permit recursive job to traverse filesystem boundaries
        (child datasets).

        .. examples(websocket)::

          Change permissions of dataset "tank/myuser" to myuser:wheel and 755.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.dataset.permission",
                "params": ["tank/myuser", {
                    "user": "myuser",
                    "acl": [],
                    "group": "builtin_users",
                    "mode": "755",
                    "options": {"recursive": true, "stripacl": true},
                }]
            }

        """
        dataset_info = await self.get_instance(id)
        path = dataset_info['mountpoint']
        acltype = dataset_info['acltype']['value']
        user = data.get('user', None)
        group = data.get('group', None)
        uid = gid = -1
        mode = data.get('mode', None)
        options = data.get('options', {})
        set_default_acl = options.pop('set_default_acl')
        acl = data.get('acl', [])

        if mode is None and set_default_acl:
            acl_template = 'POSIX_RESTRICTED' if acltype == 'POSIX' else 'NFS4_RESTRICTED'
            acl = (await self.middleware.call('filesystem.acltemplate.by_path', {
                'query-filters': [('name', '=', acl_template)],
                'format-options': {'canonicalize': True, 'ensure_builtins': True},
            }))[0]['acl']

        pjob = None

        verrors = ValidationErrors()
        if user is not None:
            try:
                uid = (await self.middleware.call('dscache.get_uncached_user', user))['pw_uid']
            except Exception as e:
                verrors.add('pool_dataset_permission.user', str(e))

        if group is not None:
            try:
                gid = (await self.middleware.call('dscache.get_uncached_group', group))['gr_gid']
            except Exception as e:
                verrors.add('pool_dataset_permission.group', str(e))

        if acl and mode:
            verrors.add('pool_dataset_permission.mode',
                        'setting mode and ACL simultaneously is not permitted.')

        if acl and options['stripacl']:
            verrors.add('pool_dataset_permissions.acl',
                        'Simultaneously setting and removing ACL is not permitted.')

        if mode and not options['stripacl']:
            if not await self.middleware.call('filesystem.acl_is_trivial', path):
                verrors.add('pool_dataset_permissions.options',
                            f'{path} has an extended ACL. The option "stripacl" must be selected.')
        verrors.check()

        if not acl and mode is None and not options['stripacl']:
            """
            Neither an ACL, mode, or removing the existing ACL are
            specified in `data`. Perform a simple chown.
            """
            options.pop('stripacl', None)
            pjob = await self.middleware.call('filesystem.chown', {
                'path': path,
                'uid': uid,
                'gid': gid,
                'options': options
            })

        elif acl:
            pjob = await self.middleware.call('filesystem.setacl', {
                'path': path,
                'dacl': acl,
                'uid': uid,
                'gid': gid,
                'options': options
            })

        elif mode or options['stripacl']:
            """
            `setperm` performs one of two possible actions. If
            `mode` is not set, but `stripacl` is specified, then
            the existing ACL on the file is converted in place via
            `acl_strip_np()`. This preserves the existing posix mode
            while removing any extended ACL entries.

            If `mode` is set, then the ACL is removed from the file
            and the new `mode` is applied.
            """
            pjob = await self.middleware.call('filesystem.setperm', {
                'path': path,
                'mode': mode,
                'uid': uid,
                'gid': gid,
                'options': options
            })
        else:
            """
            This should never occur, but fail safely to avoid undefined
            or unintended behavior.
            """
            raise CallError(f"Unexpected parameter combination: {data}",
                            errno.EINVAL)

        await pjob.wait()
        if pjob.error:
            raise CallError(pjob.error)
        return data

    # TODO: Document this please
    @accepts(
        Str('ds', required=True),
        Str('quota_type', enum=['USER', 'GROUP', 'DATASET']),
        Ref('query-filters'),
        Ref('query-options'),
    )
    @item_method
    async def get_quota(self, ds, quota_type, filters, options):
        """
        Return a list of the specified `quota_type` of  quotas on the ZFS dataset `ds`.
        Support `query-filters` and `query-options`. used_bytes and used_percentage
        may not instantly update as space is used.

        When quota_type is not DATASET, each quota entry has these fields:

        `id` - the uid or gid to which the quota applies.

        `name` - the user or group name to which the quota applies. Value is
        null if the id in the quota cannot be resolved to a user or group. This
        indicates that the user or group does not exist on the server.

        `quota` - the quota size in bytes.

        `used_bytes` - the amount of bytes the user has written to the dataset.
        A value of zero means unlimited.

        `used_percentage` - the percentage of the user or group quota consumed.

        `obj_quota` - the number of objects that may be owned by `id`.
        A value of zero means unlimited.

        `obj_used` - the number of objects currently owned by `id`.

        `obj_used_percent` - the percentage of the `obj_quota` currently used.

        Note: SMB client requests to set a quota granting no space will result
        in an on-disk quota of 1 KiB.
        """
        dataset = (await self.get_instance(ds))['name']
        quota_list = await self.middleware.call(
            'zfs.dataset.get_quota', dataset, quota_type.lower()
        )
        return filter_list(quota_list, filters, options)

    @accepts(
        Str('ds', required=True),
        List('quotas', items=[
            Dict(
                'quota_entry',
                Str('quota_type',
                    enum=['DATASET', 'USER', 'USEROBJ', 'GROUP', 'GROUPOBJ'],
                    required=True),
                Str('id', required=True),
                Int('quota_value', required=True, null=True),
            )
        ], default=[{
            'quota_type': 'USER',
            'id': '0',
            'quota_value': 0
        }])
    )
    @returns()
    @item_method
    async def set_quota(self, ds, data):
        """
        There are three over-arching types of quotas for ZFS datasets.
        1) dataset quotas and refquotas. If a DATASET quota type is specified in
        this API call, then the API acts as a wrapper for `pool.dataset.update`.

        2) User and group quotas. These limit the amount of disk space consumed
        by files that are owned by the specified users or groups. If the respective
        "object quota" type is specfied, then the quota limits the number of objects
        that may be owned by the specified user or group.

        3) Project quotas. These limit the amount of disk space consumed by files
        that are owned by the specified project. Project quotas are not yet implemended.

        This API allows users to set multiple quotas simultaneously by submitting a
        list of quotas. The list may contain all supported quota types.

        `ds` the name of the target ZFS dataset.

        `quotas` specifies a list of `quota_entry` entries to apply to dataset.

        `quota_entry` entries have these required parameters:

        `quota_type`: specifies the type of quota to apply to the dataset. Possible
        values are USER, USEROBJ, GROUP, GROUPOBJ, and DATASET. USEROBJ and GROUPOBJ
        quotas limit the number of objects consumed by the specified user or group.

        `id`: the uid, gid, or name to which the quota applies. If quota_type is
        'DATASET', then `id` must be either `QUOTA` or `REFQUOTA`.

        `quota_value`: the quota size in bytes. Setting a value of `0` removes
        the user or group quota.
        """
        MAX_QUOTAS = 100
        dataset = (await self.get_instance(ds))['name']
        verrors = ValidationErrors()
        if len(data) > MAX_QUOTAS:
            verrors.add(
                'quotas',
                f'The number of user or group quotas that can be set in single API call is limited to {MAX_QUOTAS}.'
            )

        quota_list = []
        dataset_quotas = {}

        for i, q in enumerate(data):
            quota_type = q["quota_type"].lower()
            if q["quota_type"] == 'DATASET':
                if q['id'] not in ['QUOTA', 'REFQUOTA']:
                    verrors.add(
                        f'quotas.{i}.id',
                        'id for quota_type DATASET must be either "QUOTA" or "REFQUOTA"'
                    )
                    continue

                if dataset_quotas.get(q['id'].lower()) is not None:
                    verrors.add(
                        f'quotas.{i}.id',
                        f'Setting multiple values for {q["id"]} for quota_type "DATASET" is not permitted'
                    )
                    continue

                dataset_quotas.update({
                    q['id'].lower(): q['quota_value']
                })

                continue

            if q["quota_type"] not in ['PROJECT', 'PROJECTOBJ']:
                if q['quota_value'] is None:
                    q['quota_value'] = 'none'

                xid = None

                id_type = 'user' if quota_type.startswith('user') else 'group'
                if not q["id"].isdigit():
                    try:
                        xid_obj = await self.middleware.call(f'{id_type}.get_{id_type}_obj',
                                                             {f'{id_type}name': q["id"]})
                        xid = xid_obj['pw_uid'] if id_type == 'user' else xid_obj['gr_gid']
                    except Exception:
                        self.logger.debug("Failed to convert %s [%s] to id.", id_type, q["id"], exc_info=True)
                        verrors.add(
                            f'quotas.{i}.id',
                            f'{quota_type} {q["id"]} is not valid.'
                        )
                else:
                    xid = int(q["id"])

                if xid == 0:
                    verrors.add(
                        f'quotas.{i}.id',
                        f'Setting {quota_type} quota on {id_type[0]}id [{xid}] is not permitted.'
                    )
            else:
                if not q["id"].isdigit():
                    verrors.add(
                        f'quotas.{i}.id',
                        f'{quota_type} {q["id"]} must be a numeric project id.'
                    )

            quota_list.append(f'{quota_type}quota@{q["id"]}={q["quota_value"]}')

        verrors.check()
        if dataset_quotas:
            await self.middleware.call('pool.dataset.update', ds, dataset_quotas)

        if quota_list:
            await self.middleware.call('zfs.dataset.set_quota', dataset, quota_list)

    @accepts(Str('pool'))
    @returns(Str())
    async def recommended_zvol_blocksize(self, pool):
        """
        Helper method to get recommended size for a new zvol (dataset of type VOLUME).

        .. examples(websocket)::

          Get blocksize for pool "tank".

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.dataset.recommended_zvol_blocksize",
                "params": ["tank"]
            }
        """
        pool = await self.middleware.call('pool.query', [['name', '=', pool]])
        if not pool:
            raise CallError(f'"{pool}" not found.', errno.ENOENT)

        """
        Cheatsheat for blocksizes is as follows:
        2w/3w mirror = 16K
        3wZ1, 4wZ2, 5wZ3 = 16K
        4w/5wZ1, 5w/6wZ2, 6w/7wZ3 = 32K
        6w/7w/8w/9wZ1, 7w/8w/9w/10wZ2, 8w/9w/10w/11wZ3 = 64K
        10w+Z1, 11w+Z2, 12w+Z3 = 128K

        If the zpool was forcefully created with mismatched
        vdev geometry (i.e. 3wZ1 and a 5wZ1) then we calculate
        the blocksize based on the largest vdev of the zpool.
        """
        maxdisks = 1
        for vdev in pool[0]['topology']['data']:
            if vdev['type'] == 'RAIDZ1':
                disks = len(vdev['children']) - 1
            elif vdev['type'] == 'RAIDZ2':
                disks = len(vdev['children']) - 2
            elif vdev['type'] == 'RAIDZ3':
                disks = len(vdev['children']) - 3
            elif vdev['type'] == 'MIRROR':
                disks = maxdisks
            else:
                disks = len(vdev['children'])

            if disks > maxdisks:
                maxdisks = disks

        return f'{max(16, min(128, 2 ** ((maxdisks * 8) - 1).bit_length()))}K'

    @item_method
    @accepts(Str('id', required=True))
    @returns(Ref('attachments'))
    async def attachments(self, oid):
        """
        Return a list of services dependent of this dataset.

        Responsible for telling the user whether there is a related
        share, asking for confirmation.

        Example return value:
        [
          {
            "type": "NFS Share",
            "service": "nfs",
            "attachments": ["/mnt/tank/work"]
          }
        ]
        """
        dataset = await self.get_instance(oid)
        return await self.attachments_with_path(self.__attachments_path(dataset))

    @private
    async def attachments_with_path(self, path):
        result = []
        if path:
            for delegate in self.attachment_delegates:
                attachments = {"type": delegate.title, "service": delegate.service, "attachments": []}
                for attachment in await delegate.query(path, True):
                    attachments["attachments"].append(await delegate.get_attachment_name(attachment))
                if attachments["attachments"]:
                    result.append(attachments)
        return result

    def __attachments_path(self, dataset):
        return dataset['mountpoint'] or os.path.join('/mnt', dataset['name'])

    @item_method
    @accepts(Str('id', required=True))
    @returns(Ref('processes'))
    async def processes(self, oid):
        """
        Return a list of processes using this dataset.

        Example return value:

        [
          {
            "pid": 2520,
            "name": "smbd",
            "service": "cifs"
          },
          {
            "pid": 97778,
            "name": "minio",
            "cmdline": "/usr/local/bin/minio -C /usr/local/etc/minio server --address=0.0.0.0:9000 --quiet /mnt/tank/wk"
          }
        ]
        """
        dataset = await self.get_instance(oid)
        if dataset['locked']:
            return []
        path = self.__attachments_path(dataset)
        zvol_path = f"/dev/zvol/{dataset['name']}"
        return await self.middleware.call('pool.dataset.processes_using_paths', [path, zvol_path])

    @private
    async def kill_processes(self, oid, control_services, max_tries=5):
        need_restart_services = []
        need_stop_services = []
        midpid = os.getpid()
        for process in await self.middleware.call('pool.dataset.processes', oid):
            service = process.get('service')
            if service is not None:
                if any(attachment_delegate.service == service for attachment_delegate in self.attachment_delegates):
                    need_restart_services.append(service)
                else:
                    need_stop_services.append(service)
        if (need_restart_services or need_stop_services) and not control_services:
            raise CallError('Some services have open files and need to be restarted or stopped', errno.EBUSY, {
                'code': 'control_services',
                'restart_services': need_restart_services,
                'stop_services': need_stop_services,
                'services': need_restart_services + need_stop_services,
            })

        for i in range(max_tries):
            processes = await self.middleware.call('pool.dataset.processes', oid)
            if not processes:
                return

            for process in processes:
                if process["pid"] == midpid:
                    self.logger.warning("The main middleware process %r (%r) currently is holding dataset %r",
                                        process['pid'], process['cmdline'], oid)
                    continue

                service = process.get('service')
                if service is not None:
                    if any(attachment_delegate.service == service for attachment_delegate in self.attachment_delegates):
                        self.logger.info('Restarting service %r that holds dataset %r', service, oid)
                        await self.middleware.call('service.restart', service)
                    else:
                        self.logger.info('Stopping service %r that holds dataset %r', service, oid)
                        await self.middleware.call('service.stop', service)
                else:
                    self.logger.info('Killing process %r (%r) that holds dataset %r', process['pid'],
                                     process['cmdline'], oid)
                    try:
                        await self.middleware.call('service.terminate_process', process['pid'])
                    except CallError as e:
                        self.logger.warning('Error killing process: %r', e)

        processes = await self.middleware.call('pool.dataset.processes', oid)
        if not processes:
            return

        self.logger.info('The following processes don\'t want to stop: %r', processes)
        raise CallError('Unable to stop processes that have open files', errno.EBUSY, {
            'code': 'unstoppable_processes',
            'processes': processes,
        })

    @private
    def register_attachment_delegate(self, delegate):
        self.attachment_delegates.append(delegate)

    @private
    async def query_attachment_delegate(self, name, path, enabled):
        for delegate in self.attachment_delegates:
            if delegate.name == name:
                return await delegate.query(path, enabled)

        raise RuntimeError(f'Unknown attachment delegate {name!r}')


class PoolScrubModel(sa.Model):
    __tablename__ = 'storage_scrub'

    id = sa.Column(sa.Integer(), primary_key=True)
    scrub_volume_id = sa.Column(sa.Integer(), sa.ForeignKey('storage_volume.id', ondelete='CASCADE'))
    scrub_threshold = sa.Column(sa.Integer(), default=35)
    scrub_description = sa.Column(sa.String(200))
    scrub_minute = sa.Column(sa.String(100), default="00")
    scrub_hour = sa.Column(sa.String(100), default="00")
    scrub_daymonth = sa.Column(sa.String(100), default="*")
    scrub_month = sa.Column(sa.String(100), default='*')
    scrub_dayweek = sa.Column(sa.String(100), default="7")
    scrub_enabled = sa.Column(sa.Boolean(), default=True)


class PoolScrubService(CRUDService):

    class Config:
        datastore = 'storage.scrub'
        datastore_extend = 'pool.scrub.pool_scrub_extend'
        datastore_prefix = 'scrub_'
        namespace = 'pool.scrub'
        cli_namespace = 'storage.scrub'

    ENTRY = Dict(
        'pool_scrub_entry',
        Int('pool', validators=[Range(min=1)], required=True),
        Int('threshold', validators=[Range(min=0)], required=True),
        Str('description', required=True),
        Cron(
            'schedule',
            defaults={
                'minute': '00',
                'hour': '00',
                'dow': '7'
            },
            required=True,
        ),
        Bool('enabled', default=True, required=True),
        Int('id', required=True),
        Str('pool_name', required=True),
        register=True
    )

    @private
    async def pool_scrub_extend(self, data):
        pool = data.pop('volume')
        data['pool'] = pool['id']
        data['pool_name'] = pool['vol_name']
        Cron.convert_db_format_to_schedule(data)
        return data

    @private
    async def validate_data(self, data, schema):
        verrors = ValidationErrors()

        pool_pk = data.get('pool')
        if pool_pk:
            pool_obj = await self.middleware.call(
                'datastore.query',
                'storage.volume',
                [('id', '=', pool_pk)]
            )

            if len(pool_obj) == 0:
                verrors.add(
                    f'{schema}.pool',
                    'The specified volume does not exist'
                )
            elif (
                    'id' not in data.keys() or
                    (
                        'id' in data.keys() and
                        'original_pool_id' in data.keys() and
                        pool_pk != data['original_pool_id']
                    )
            ):
                scrub_obj = await self.query(filters=[('pool', '=', pool_pk)])
                if len(scrub_obj) != 0:
                    verrors.add(
                        f'{schema}.pool',
                        'A scrub with this pool already exists'
                    )

        return verrors, data

    @accepts(
        Patch(
            'pool_scrub_entry', 'pool_scrub_entry',
            ('rm', {'name': 'id'}),
            ('rm', {'name': 'pool_name'}),
            ('edit', {'name': 'threshold', 'method': lambda x: setattr(x, 'required', False)}),
            ('edit', {'name': 'schedule', 'method': lambda x: setattr(x, 'required', False)}),
            ('edit', {'name': 'description', 'method': lambda x: setattr(x, 'required', False)}),
        )
    )
    async def do_create(self, data):
        """
        Create a scrub task for a pool.

        `threshold` refers to the minimum amount of time in days has to be passed before
        a scrub can run again.

        .. examples(websocket)::

          Create a scrub task for pool of id 1, to run every sunday but with a threshold of
          35 days.
          The check will run at 3AM every sunday.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.scrub.create"
                "params": [{
                    "pool": 1,
                    "threshold": 35,
                    "description": "Monthly scrub for tank",
                    "schedule": "0 3 * * 7",
                    "enabled": true
                }]
            }
        """
        verrors, data = await self.validate_data(data, 'pool_scrub_create')
        verrors.check()

        data['volume'] = data.pop('pool')
        Cron.convert_schedule_to_db_format(data)

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('service.restart', 'cron')

        return await self.get_instance(data['id'])

    async def do_update(self, id, data):
        """
        Update scrub task of `id`.
        """
        task_data = await self.get_instance(id)
        original_data = task_data.copy()
        task_data['original_pool_id'] = original_data['pool']
        task_data.update(data)
        verrors, task_data = await self.validate_data(task_data, 'pool_scrub_update')
        verrors.check()

        task_data.pop('original_pool_id')
        Cron.convert_schedule_to_db_format(task_data)
        Cron.convert_schedule_to_db_format(original_data)

        if len(set(task_data.items()) ^ set(original_data.items())) > 0:

            task_data['volume'] = task_data.pop('pool')
            task_data.pop('pool_name', None)

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                id,
                task_data,
                {'prefix': self._config.datastore_prefix}
            )

            await self.middleware.call('service.restart', 'cron')

        return await self.get_instance(id)

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete scrub task of `id`.
        """
        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        await self.middleware.call('service.restart', 'cron')
        return response

    @accepts(
        Str('name', required=True),
        Str('action', enum=['START', 'STOP', 'PAUSE'], default='START')
    )
    @returns()
    @job(lock=lambda i: f'{i[0]}-{i[1] if len(i) >= 2 else "START"}')
    async def scrub(self, job, name, action):
        """
        Start/Stop/Pause a scrub on pool `name`.
        """
        await self.middleware.call('zfs.pool.scrub_action', name, action)

        if action == 'START':
            while True:
                scrub = await self.middleware.call('zfs.pool.scrub_state', name)

                if scrub['pause']:
                    job.set_progress(100, 'Scrub paused')
                    break

                if scrub['function'] != 'SCRUB':
                    break

                if scrub['state'] == 'FINISHED':
                    job.set_progress(100, 'Scrub finished')
                    break

                if scrub['state'] == 'CANCELED':
                    break

                if scrub['state'] == 'SCANNING':
                    job.set_progress(scrub['percentage'], 'Scrubbing')

                await asyncio.sleep(1)

    @accepts(Str('name'), Int('threshold', default=35))
    @returns()
    async def run(self, name, threshold):
        """
        Initiate a scrub of a pool `name` if last scrub was performed more than `threshold` days before.
        """
        await self.middleware.call('alert.oneshot_delete', 'ScrubNotStarted', name)
        await self.middleware.call('alert.oneshot_delete', 'ScrubStarted', name)
        try:
            started = await self.__run(name, threshold)
        except ScrubError as e:
            await self.middleware.call('alert.oneshot_create', 'ScrubNotStarted', {
                'pool': name,
                'text': e.errmsg,
            })
        else:
            if started:
                await self.middleware.call('alert.oneshot_create', 'ScrubStarted', name)

    async def __run(self, name, threshold):
        if name == await self.middleware.call('boot.pool_name'):
            pool = await self.middleware.call('zfs.pool.query', [['name', '=', name]], {'get': True})
        else:
            if await self.middleware.call('failover.licensed'):
                if await self.middleware.call('failover.status') == 'BACKUP':
                    return

            pool = await self.middleware.call('pool.query', [['name', '=', name]], {'get': True})
            if pool['status'] == 'OFFLINE':
                raise ScrubError(f'Pool {name} is offline, not running scrub')

        if pool['scan']['state'] == 'SCANNING':
            return False

        history = (await run('zpool', 'history', name, encoding='utf-8')).stdout
        for match in reversed(list(RE_HISTORY_ZPOOL_SCRUB.finditer(history))):
            last_scrub = datetime.strptime(match.group(1), '%Y-%m-%d.%H:%M:%S')
            break
        else:
            # creation time of the pool if no scrub was done
            for match in RE_HISTORY_ZPOOL_CREATE.finditer(history):
                last_scrub = datetime.strptime(match.group(1), '%Y-%m-%d.%H:%M:%S')
                break
            else:
                logger.warning("Could not find last scrub of pool %r", name)
                last_scrub = datetime.min

        if (datetime.now() - last_scrub).total_seconds() < (threshold - 1) * 86400:
            logger.debug("Pool %r last scrub %r", name, last_scrub)
            return False

        await self.middleware.call('pool.scrub.scrub', pool['name'])
        return True


def setup(middleware):
    asyncio.ensure_future(middleware.call('pool.configure_resilver_priority'))
