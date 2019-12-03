import asyncio
import base64
import contextlib
import enum
import errno
import json
import logging
from datetime import datetime, time
import os
import re
import secrets
import shutil
import subprocess
try:
    import sysctl
except ImportError:
    sysctl = None
import tempfile

try:
    import bsd
except ImportError:
    bsd = None
import psutil

from collections import defaultdict

from libzfs import ZFSException
from middlewared.job import JobProgressBuffer, Pipes
from middlewared.plugins.zfs import ZFSSetPropertyError
from middlewared.schema import (
    accepts, Attribute, Bool, Cron, Dict, EnumMixin, Int, List, Patch, Str, UnixPerm, Any, Ref,
)
from middlewared.service import (
    ConfigService, filterable, item_method, job, private, CallError, CRUDService, ValidationErrors, periodic
)
from middlewared.service_exception import ValidationError
import middlewared.sqlalchemy as sa
from middlewared.utils import Popen, filter_list, run, start_daemon_thread
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.utils.shell import join_commandline
from middlewared.validators import Match, Range, Time

logger = logging.getLogger(__name__)

GELI_KEYPATH = '/data/geli'
RE_DISKPART = re.compile(r'^([a-z]+\d+)(p\d+)?')
RE_HISTORY_ZPOOL_SCRUB = re.compile(r'^([0-9\.\:\-]{19})\s+zpool scrub', re.MULTILINE)
RE_HISTORY_ZPOOL_CREATE = re.compile(r'^([0-9\.\:\-]{19})\s+zpool create', re.MULTILINE)
ZPOOL_CACHE_FILE = '/data/zfs/zpool.cache'
ZPOOL_KILLCACHE = '/data/zfs/killcache'


class ZFSKeyFormat(enum.Enum):
    HEX = 'HEX'
    PASSPHRASE = 'PASSPHRASE'
    RAW = 'RAW'


class Inheritable(EnumMixin, Attribute):
    def __init__(self, *args, **kwargs):
        self.value = kwargs.pop('value')
        super(Inheritable, self).__init__(*args, **kwargs)

    def clean(self, value):
        if value == 'INHERIT':
            return value

        return self.value.clean(value)

    def validate(self, value):
        if value == 'INHERIT':
            return

        return self.value.validate(value)

    def to_json_schema(self, parent=None):
        schema = self.value.to_json_schema(parent)
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


async def is_mounted(middleware, path):
    mounted = await middleware.run_in_thread(bsd.getmntinfo)
    return any(fs.dest == path for fs in mounted)


async def mount(device, path, fs_type, fs_options, options):
    options = options or []

    if isinstance(device, str):
        device = device.encode("utf-8")

    if isinstance(path, str):
        path = path.encode("utf-8")

    executable = "/sbin/mount"
    arguments = []

    if fs_type == "ntfs":
        executable = "/usr/local/bin/ntfs-3g"
    elif fs_type == "msdosfs" and fs_options:
        executable = "/sbin/mount_msdosfs"
        if fs_options.get("locale"):
            arguments.extend(["-L", fs_options["locale"]])
        arguments.extend(sum([["-o", option] for option in options], []))
        options = []
    else:
        arguments.extend(["-t", fs_type])

    if options:
        arguments.extend(["-o", ",".join(options)])

    proc = await Popen(
        [executable] + arguments + [device, path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf8",
    )
    output = await proc.communicate()

    if proc.returncode != 0:
        logger.debug("Mount failed (%s): %s", proc.returncode, output)
        raise ValueError("Mount failed (exit code {0}):\n{1}{2}" .format(
            proc.returncode,
            output[0].decode("utf-8"),
            output[1].decode("utf-8"),
        ))
    else:
        return True


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

    @accepts(
        Dict(
            'pool_resilver',
            Str('begin', validators=[Time()]),
            Str('end', validators=[Time()]),
            Bool('enabled'),
            List('weekday', items=[Int('weekday', validators=[Range(min=1, max=7)])])
        )
    )
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
        if verrors:
            raise verrors

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


class KernelModuleContextManager:
    def __init__(self, module):
        self.module = module

    async def __aenter__(self):
        if self.module is not None:
            if not await self.module_loaded():
                await run('kldload', self.module, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if not await self.module_loaded():
                    raise Exception('Kernel module %r failed to load', self.module)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.module is not None:
            try:
                await run('kldunload', self.module, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    async def module_loaded(self):
        return (await run('kldstat', '-n', self.module, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)).returncode == 0


class MountFsContextManager:
    def __init__(self, middleware, device, path, *args, **kwargs):
        self.middleware = middleware
        self.device = device
        self.path = path
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        await mount(self.device, self.path, *self.args, **self.kwargs)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if await is_mounted(self.middleware, self.path):
            await self.middleware.run_in_thread(bsd.unmount, self.path)


class PoolModel(sa.Model):
    __tablename__ = 'storage_volume'

    id = sa.Column(sa.Integer(), primary_key=True)
    vol_name = sa.Column(sa.String(120))
    vol_guid = sa.Column(sa.String(50))
    vol_encrypt = sa.Column(sa.Integer(), default=0)
    vol_encryptkey = sa.Column(sa.String(50))


class EncryptedDiskModel(sa.Model):
    __tablename__ = 'storage_encrypteddisk'

    id = sa.Column(sa.Integer(), primary_key=True)
    encrypted_volume_id = sa.Column(sa.ForeignKey('storage_volume.id', ondelete='CASCADE'))
    encrypted_disk_id = sa.Column(sa.ForeignKey('storage_disk.disk_identifier', ondelete='SET NULL'), nullable=True)
    encrypted_provider = sa.Column(sa.String(120))


class PoolService(CRUDService):

    GELI_KEYPATH = '/data/geli'

    class Config:
        datastore = 'storage.volume'
        datastore_extend = 'pool.pool_extend'
        datastore_prefix = 'vol_'

    @item_method
    @accepts(
        Int('id', required=True),
        Str('action', enum=['START', 'STOP', 'PAUSE'], required=True)
    )
    @job()
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
        pool = await self._get_instance(oid)
        return await job.wrap(
            await self.middleware.call('zfs.pool.scrub', pool['name'], action)
        )

    @accepts(List('types', items=[Str('type', enum=['FILESYSTEM', 'VOLUME'])], default=['FILESYSTEM', 'VOLUME']))
    async def filesystem_choices(self, types):
        """
        Returns all available datasets, except system datasets.

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
                    ('name', 'rnin', '.system'),
                    ('pool', 'in', vol_names),
                    ('type', 'in', types),
                ],
                {'extra': {'retrieve_properties': False}},
            )
        ]

    @accepts(Int('id', required=True))
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
        name = (await self._get_instance(oid))['name']
        proc = await Popen(
            f'zpool get -H -o value version {name}',
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8', shell=True
        )
        res, err = await proc.communicate()
        if proc.returncode != 0:
            return True
        res = res.decode('utf8').rstrip('\n')
        try:
            int(res)
        except ValueError:

            if res == '-':
                proc = await Popen(
                    f"zpool get -H -o property,value all {name}",
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8', shell=True
                )
                data = (await proc.communicate())[0].decode('utf8').strip('\n')
                for line in [l for l in data.split('\n') if l.startswith('feature') and '\t' in l]:
                    prop, value = line.split('\t', 1)
                    if value not in ('active', 'enabled'):
                        return False
                return True
            else:
                return False
        else:
            return False

    @accepts(Int('id'))
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
            (await self._get_instance(oid))['name']
        )
        return True

    def _topology(self, x, geom_scan=True):
        """
        Transform topology output from libzfs to add `device` and make `type` uppercase.
        """
        if isinstance(x, dict):
            path = x.get('path')
            if path is not None:
                device = None
                if path.startswith('/dev/'):
                    device = self.middleware.call_sync('disk.label_to_dev', path[5:], geom_scan)
                x['device'] = device
                x['disk'] = RE_DISKPART.sub(r'\1', device) if device else None
            for key in x:
                if key == 'type' and isinstance(x[key], str):
                    x[key] = x[key].upper()
                else:
                    x[key] = self._topology(x[key], False)
        elif isinstance(x, list):
            for i, entry in enumerate(x):
                x[i] = self._topology(x[i], False)
        return x

    @private
    def pool_extend(self, pool):

        """
        If pool is encrypted we need to check if the pool is imported
        or if all geli providers exist.
        """
        pool['path'] = f'/mnt/{pool["name"]}'
        try:
            zpool = self.middleware.call_sync('zfs.pool.query', [('id', '=', pool['name'])])[0]
        except Exception:
            zpool = None

        if zpool:
            pool.update({
                'status': zpool['status'],
                'scan': zpool['scan'],
                'topology': self._topology(zpool['groups']),
                'healthy': zpool['healthy'],
                'status_detail': zpool['status_detail'],
            })
        else:
            pool.update({
                'status': 'OFFLINE',
                'scan': None,
                'topology': None,
                'healthy': False,
                'status_detail': None,
            })

        if pool['encrypt'] > 0:
            if zpool:
                pool['is_decrypted'] = True
            else:
                decrypted = True
                for ed in self.middleware.call_sync('datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]):
                    if not os.path.exists(f'/dev/{ed["encrypted_provider"]}.eli'):
                        decrypted = False
                        break
                pool['is_decrypted'] = decrypted
            pool['encryptkey_path'] = os.path.join(GELI_KEYPATH, f'{pool["encryptkey"]}.key')
        else:
            pool['encryptkey_path'] = None
            pool['is_decrypted'] = True
        return pool

    @accepts(
        Int('oid'),
        Dict(
            'pool_attach',
            Str('target_vdev', reuired=True),
            Str('new_disk', reuired=True),
            Str('passphrase'),
        )
    )
    @job(lock=lambda args: f'pool_attach_{args[0]}')
    async def attach(self, job, oid, options):
        """
        If the `oid` pool is passphrase GELI encrypted, `passphrase` must be specified for this operation to succeed.

        `new_disk` is the devname of the new disk to be attached.

        `target_vdev` is the GUID of the vdev where the disk needs to be attached. In case of STRIPED vdev, this
        is the STRIPED disk GUID which will be converted to mirror. If `target_vdev` is mirror, it will be coverted
        into a n-way mirror.
        """
        pool = await self._get_instance(oid)
        verrors = ValidationErrors()
        if not pool['is_decrypted']:
            verrors.add('oid', 'Pool must be unlocked for this action.')
            verrors.check()
        topology = pool['topology']
        topology_type = vdev = None
        for i in topology:
            for v in topology[i]:
                if v['guid'] == options['target_vdev']:
                    topology_type = i
                    vdev = v
                    break
            if topology_type:
                break
        else:
            verrors.add('pool_attach.target_vdev', 'Unable to locate VDEV')
            verrors.check()
        if topology_type in ('cache', 'spares'):
            verrors.add('pool_attach.target_vdev', f'Attaching disks to {topology_type} not allowed.')
        elif topology_type == 'data':
            # We would like to make sure here that we don't have inconsistent vdev types across data
            if vdev['type'] not in ('DISK', 'MIRROR'):
                verrors.add('pool_attach.target_vdev', f'Attaching disk to {vdev["type"]} vdev is not allowed.')

        if pool['encrypt'] == 2:
            if not options.get('passphrase'):
                verrors.add('pool_attach.passphrase', 'Passphrase is required for encrypted pool.')
            elif not await self.middleware.call('disk.geli_testkey', pool, options['passphrase']):
                verrors.add('pool_attach.passphrase', 'Passphrase is not valid.')

        # Let's validate new disk now
        await self.__check_disks_availability(verrors, {options['new_disk']: options['new_disk']}, 'pool_attach')
        verrors.check()

        guid = vdev['guid'] if vdev['type'] == 'DISK' else vdev['children'][0]['guid']
        disks = {options['new_disk']: {'create_swap': topology_type == 'data', 'vdev': []}}
        passphrase_path = None
        if options.get('passphrase'):
            passf = tempfile.NamedTemporaryFile(mode='w+', dir='/tmp/')
            os.chmod(passf.name, 0o600)
            passf.write(options['passphrase'])
            passf.flush()
            passphrase_path = passf.name
        try:
            enc_disks = await self.__format_disks(job, disks, pool['encryptkey_path'], passphrase_path)
        finally:
            if passphrase_path:
                passf.close()

        devname = disks[options['new_disk']]['vdev'][0]
        extend_job = await self.middleware.call('zfs.pool.extend', pool['name'], None, [
            {'target': guid, 'type': 'DISK', 'path': devname}
        ])
        try:
            await job.wrap(extend_job)
        except CallError:
            if pool['encrypt'] > 0:
                try:
                    # If replace has failed lets detach geli to not keep disk busy
                    await self.middleware.call('disk.geli_detach_single', devname)
                except Exception:
                    self.logger.warn(f'Failed to geli detach {devname}', exc_info=True)
            raise

        disk = await self.middleware.call('disk.query', [['devname', '=', options['new_disk']]], {'get': True})
        await self.__save_encrypteddisks(oid, enc_disks, {disk['devname']: disk})
        await self.middleware.call('disk.swaps_configure')

    @accepts(Dict(
        'pool_create',
        Str('name', required=True),
        Bool('encryption', default=False),
        Str('deduplication', enum=[None, 'ON', 'VERIFY', 'OFF'], default=None, null=True),
        Dict(
            'encryption_options',
            Bool('generate_key', default=False),
            Int('pbkdf2iters', default=350000, validators=[Range(min=100000)]),
            Str(
                'algorithm', default='AES-256-CCM', enum=[
                    'AES-128-CCM', 'AES-192-CCM', 'AES-256-CCM', 'AES-128-GCM', 'AES-192-GCM', 'AES-256-GCM'
                ]
            ),
            Str('passphrase', default=None, null=True, empty=False, private=True),
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
            List('spares', items=[Str('disk')], default=[]),
            required=True,
        ),
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
                    {"type": "RAIDZ1", "disks": ["da5"]}
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

        if not data['topology']['data']:
            verrors.add('pool_create.topology.data', 'At least one data vdev is required')

        encryption_dict = await self.middleware.call(
            'pool.dataset.validate_encryption_data', None, verrors, {
                'enabled': data.pop('encryption'), **data.pop('encryption_options'), 'key_file': False,
            }, 'pool_create.encryption_options',
        )

        await self.__common_validation(verrors, data, 'pool_create')
        disks, vdevs = await self.__convert_topology_to_vdevs(data['topology'])
        disks_cache = await self.__check_disks_availability(verrors, disks)

        if verrors:
            raise verrors

        formatted_disks = await self.__format_disks(job, disks)

        options = {
            'feature@lz4_compress': 'enabled',
            'altroot': '/mnt',
            'cachefile': ZPOOL_CACHE_FILE,
            'failmode': 'continue',
            'autoexpand': 'on',
        }

        fsoptions = {
            'compression': 'lz4',
            'aclinherit': 'passthrough',
            'mountpoint': f'/{data["name"]}',
            **encryption_dict
        }

        dedup = data.get('deduplication')
        if dedup:
            fsoptions['dedup'] = dedup.lower()

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

            encrypted_dataset_pk = await self.middleware.call(
                'pool.dataset.insert_or_update_encrypted_record', {
                    'name': data['name'], 'encryption_key': encryption_dict.get('key'),
                    'key_format': encryption_dict.get('keyformat')
                }
            )

            await self.__save_encrypteddisks(pool_id, formatted_disks, disks_cache)

            await self.middleware.call(
                'datastore.insert',
                'storage.scrub',
                {'volume': pool_id},
                {'prefix': 'scrub_'},
            )
        except Exception as e:
            # Something wrong happened, we need to rollback and destroy pool.
            if z_pool:
                try:
                    await self.middleware.call('zfs.pool.delete', data['name'])
                except Exception:
                    self.logger.warn('Failed to delete pool on pool.create rollback', exc_info=True)
            if pool_id:
                await self.middleware.call('datastore.delete', 'storage.volume', pool_id)
            if encrypted_dataset_pk:
                await self.middleware.call('datastore.delete', PoolDatasetService.dataset_store, encrypted_dataset_pk)
            raise e

        # There is really no point in waiting all these services to reload so do them
        # in background.
        async def restart_services():
            await self.middleware.call('service.reload', 'disk')
            if (
                await self.middleware.call('systemdataset.config')
            )['pool'] == await self.middleware.call('boot.pool_name'):
                await self.middleware.call('service.restart', 'system_datasets')
            # regenerate crontab because of scrub
            await self.middleware.call('service.restart', 'cron')

        asyncio.ensure_future(restart_services())

        pool = await self._get_instance(pool_id)
        await self.middleware.call_hook('pool.post_create_or_update', pool=pool)
        return pool

    @accepts(Int('id'), Patch(
        'pool_create', 'pool_update',
        ('rm', {'name': 'name'}),
        ('rm', {'name': 'encryption'}),
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
        pool = await self._get_instance(id)

        verrors = ValidationErrors()

        await self.__common_validation(verrors, data, 'pool_update', old=pool)
        disks, vdevs = await self.__convert_topology_to_vdevs(data['topology'])
        disks_cache = await self.__check_disks_availability(verrors, disks, 'pool_update')

        if verrors:
            raise verrors

        if pool['encryptkey']:
            enc_keypath = os.path.join(GELI_KEYPATH, f'{pool["encryptkey"]}.key')
        else:
            enc_keypath = None

        enc_disks = await self.__format_disks(job, disks, enc_keypath)

        job.set_progress(90, 'Extending ZFS Pool')

        extend_job = await self.middleware.call('zfs.pool.extend', pool['name'], vdevs)
        await extend_job.wait()

        if extend_job.error:
            raise CallError(extend_job.error)

        await self.__save_encrypteddisks(id, enc_disks, disks_cache)

        if pool['encrypt'] >= 2:
            # FIXME: ask current passphrase and validate
            await self.middleware.call('disk.geli_passphrase', pool, None)
            await self.middleware.call(
                'datastore.update', 'storage.volume', id, {'encrypt': 1}, {'prefix': 'vol_'},
            )

        pool = await self._get_instance(id)
        await self.middleware.call_hook('pool.post_create_or_update', pool=pool)
        return pool

    async def __common_validation(self, verrors, data, schema_name, old=None):
        topology_data = list(data['topology'].get('data') or [])

        if old:
            def disk_to_stripe():
                """
                We need to convert the original topology to use STRIPE
                instead of DISK to match the user input data
                """
                rv = []
                spare = None
                for i in old['topology']['data']:
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

            topology_data += disk_to_stripe()
        lastdatatype = None
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
                    f'{schema_name}.topology.data.{i}.disks',
                    f'You need at least {mindisks} disk(s) for this vdev type.',
                )

            if lastdatatype and lastdatatype != vdev['type']:
                verrors.add(
                    f'{schema_name}.topology.data.{i}.type',
                    'You are not allowed to create a pool with different data vdev types '
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
        for i in ('data', 'cache', 'log'):
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

    async def __check_disks_availability(self, verrors, disks, schema='pool_create'):
        """
        Makes sure the disks are present in the system and not reserved
        by anything else (boot, pool, iscsi, etc).

        Returns:
            dict - disk.query for all disks
        """
        disks_cache = dict(map(
            lambda x: (x['devname'], x),
            await self.middleware.call(
                'disk.query', [('devname', 'in', list(disks.keys()))]
            )
        ))

        disks_set = set(disks.keys())
        disks_not_in_cache = disks_set - set(disks_cache.keys())
        if disks_not_in_cache:
            verrors.add(
                f'{schema}.topology',
                f'The following disks were not found in system: {"," .join(disks_not_in_cache)}.'
            )

        disks_reserved = await self.middleware.call('disk.get_reserved')
        disks_reserved = disks_set - (disks_set - set(disks_reserved))
        if disks_reserved:
            verrors.add(
                f'{schema}.topology',
                f'The following disks are already in use: {"," .join(disks_reserved)}.'
            )
        return disks_cache

    async def __format_disks(self, job, disks, enc_keypath=None, passphrase=None):
        """
        Format all disks, putting all freebsd-zfs partitions created
        into their respectives vdevs.
        """

        # Make sure all SED disks are unlocked
        await self.middleware.call('disk.sed_unlock_all')

        swapgb = (await self.middleware.call('system.advanced.config'))['swapondrive']

        enc_disks = []
        formatted = 0

        async def format_disk(arg):
            nonlocal enc_disks, formatted
            disk, config = arg
            await self.middleware.call(
                'disk.format', disk, swapgb if config['create_swap'] else 0, False,
            )
            devname = await self.middleware.call('disk.gptid_from_part_type', disk, 'freebsd-zfs')
            if enc_keypath:
                enc_disks.append({
                    'disk': disk,
                    'devname': devname,
                })
                devname = await self.middleware.call('disk.encrypt', devname, enc_keypath, passphrase)
            formatted += 1
            job.set_progress(15, f'Formatting disks ({formatted}/{len(disks)})')
            config['vdev'].append(f'/dev/{devname}')

        job.set_progress(15, f'Formatting disks (0/{len(disks)})')
        await asyncio_map(format_disk, disks.items(), limit=16)

        await self.middleware.call('disk.sync_all')

        return enc_disks

    async def __save_encrypteddisks(self, pool_id, enc_disks, disks_cache):
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
    @accepts(Int('id', required=False, default=None, null=True))
    async def get_disks(self, oid):
        """
        Get all disks in use by pools.
        If `id` is provided only the disks from the given pool `id` will be returned.
        """
        filters = []
        if oid:
            filters.append(('id', '=', oid))
        for pool in await self.query(filters):
            if pool['is_decrypted'] and pool['status'] != 'OFFLINE':
                for i in await self.middleware.call('zfs.pool.get_disks', pool['name']):
                    yield i
            else:
                for encrypted_disk in await self.middleware.call(
                    'datastore.query',
                    'storage.encrypteddisk',
                    [('encrypted_volume', '=', pool['id'])]
                ):
                    # Use provider and not disk because a disk is not a guarantee
                    # to point to correct device if its locked and its not in the system
                    # (e.g. temporarily). See #50291
                    prov = encrypted_disk["encrypted_provider"]
                    if not prov:
                        continue

                    disk_name = await self.middleware.call('disk.label_to_disk', prov)
                    if not disk_name:
                        continue

                    disk = await self.middleware.call('disk.query', [('name', '=', disk_name)])
                    if not disk:
                        continue
                    disk = disk[0]

                    if os.path.exists(os.path.join("/dev", disk['devname'])):
                        yield disk['devname']

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
        Str('disk', required=True),
        Bool('force', default=False),
        Str('passphrase', private=True),
    ))
    @job(lock='pool_replace')
    async def replace(self, job, oid, options):
        """
        Replace a disk on a pool.

        `label` is the ZFS guid or a device name
        `disk` is the identifier of a disk

        .. examples(websocket)::

          Replace missing ZFS device with disk {serial}FOO.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.replace",
                "params": [1, {
                    "label": "80802394992848654",
                    "disk": "{serial}FOO"
                }]
            }
        """
        pool = await self._get_instance(oid)

        verrors = ValidationErrors()

        unused_disks = await self.middleware.call('disk.get_unused')
        disk = list(filter(lambda x: x['identifier'] == options['disk'], unused_disks))
        if not disk:
            verrors.add('options.disk', 'Disk not found.', errno.ENOENT)
        else:
            disk = disk[0]

            if not options['force'] and not await self.middleware.call(
                'disk.check_clean', disk['devname']
            ):
                verrors.add('options.force', 'Disk is not clean, partitions were found.')

        if pool['encrypt'] == 2:
            if not options.get('passphrase'):
                verrors.add('options.passphrase', 'Passphrase is required for encrypted pool.')
            elif not await self.middleware.call(
                'disk.geli_testkey', pool, options['passphrase']
            ):
                verrors.add('options.passphrase', 'Passphrase is not valid.')

        found = self.__find_disk_from_topology(options['label'], pool)

        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found.', errno.ENOENT)

        if verrors:
            raise verrors

        if found[0] in ('data', 'spare'):
            create_swap = True
        else:
            create_swap = False

        swap_disks = [disk['devname']]
        # If the disk we are replacing is still available, remove it from swap as well
        if found[1] and os.path.exists(found[1]['path']):
            from_disk = await self.middleware.call(
                'disk.label_to_disk', found[1]['path'].replace('/dev/', '')
            )
            if from_disk:
                swap_disks.append(from_disk)

        await self.middleware.call('disk.swaps_remove_disks', swap_disks)

        vdev = []
        passphrase_path = None
        if options.get('passphrase'):
            passf = tempfile.NamedTemporaryFile(mode='w+', dir='/tmp/')
            os.chmod(passf.name, 0o600)
            passf.write(options['passphrase'])
            passf.flush()
            passphrase_path = passf.name
        try:
            enc_disks = await self.__format_disks(
                job,
                {disk['devname']: {'vdev': vdev, 'create_swap': create_swap}},
                pool['encryptkey_path'],
                passphrase_path,
            )
        finally:
            if passphrase_path:
                passf.close()

        new_devname = vdev[0].replace('/dev/', '')

        try:
            await self.middleware.call(
                'zfs.pool.replace', pool['name'], options['label'], new_devname
            )
            # If we are replacing a faulted disk, kick it right after replace
            # is initiated.
            try:
                vdev = await self.middleware.call(
                    'zfs.pool.get_vdev', pool['name'], options['label'],
                )
                if vdev['status'] not in ('ONLINE', 'DEGRADED'):
                    await self.middleware.call('zfs.pool.detach', pool['name'], options['label'])
            except Exception:
                self.logger.warn('Failed to detach device', exc_info=True)
        except Exception as e:
            try:
                # If replace has failed lets detach geli to not keep disk busy
                await self.middleware.call('disk.geli_detach_single', new_devname)
            except Exception:
                self.logger.warn(f'Failed to geli detach {new_devname}', exc_info=True)
            raise e
        finally:
            # Needs to happen even if replace failed to put back disk that had been
            # removed from swap prior to replacement
            await self.middleware.call('disk.swaps_configure')

        await self.__save_encrypteddisks(oid, enc_disks, {disk['devname']: disk})

        return True

    def __find_disk_from_topology(self, label, pool):
        check = []
        found = None
        for root, children in pool['topology'].items():
            check.append((root, children))

        while check:
            root, children = check.pop()
            for c in children:
                if c['type'] == 'DISK':
                    if label in (c['path'].replace('/dev/', ''), c['guid']):
                        found = (root, c)
                        break
                if c['children']:
                    check.append((root, c['children']))
        return found

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
    ))
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
        pool = await self._get_instance(oid)

        verrors = ValidationErrors()
        found = self.__find_disk_from_topology(options['label'], pool)
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found on this pool.')
        if verrors:
            raise verrors

        disk = await self.middleware.call(
            'disk.label_to_disk', found[1]['path'].replace('/dev/', '')
        )
        if disk:
            await self.middleware.call('disk.swaps_remove_disks', [disk])

        await self.middleware.call('zfs.pool.detach', pool['name'], found[1]['guid'])

        await self.middleware.call('pool.sync_encrypted', oid)

        if disk:
            await self.middleware.call('disk.unlabel', disk)

        return True

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
    ))
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
        pool = await self._get_instance(oid)

        verrors = ValidationErrors()
        found = self.__find_disk_from_topology(options['label'], pool)
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found on this pool.')
        if verrors:
            raise verrors

        disk = await self.middleware.call(
            'disk.label_to_disk', found[1]['path'].replace('/dev/', '')
        )
        await self.middleware.call('disk.swaps_remove_disks', [disk])

        await self.middleware.call('zfs.pool.offline', pool['name'], found[1]['guid'])

        if found[1]['path'].endswith('.eli'):
            devname = found[1]['path'].replace('/dev/', '')[:-4]
            await self.middleware.call('disk.geli_detach_single', devname)
            await self.middleware.call(
                'datastore.delete',
                'storage.encrypteddisk',
                [('encrypted_volume', '=', oid), ('encrypted_provider', '=', devname)],
            )
        return True

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
    ))
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
        pool = await self._get_instance(oid)

        verrors = ValidationErrors()

        found = self.__find_disk_from_topology(options['label'], pool)
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found on this pool.')

        if pool['encrypt'] > 0:
            verrors.add('id', 'Disk cannot be set to online in encrypted pool.')

        if verrors:
            raise verrors

        await self.middleware.call('zfs.pool.online', pool['name'], found[1]['guid'])

        disk = await self.middleware.call(
            'disk.label_to_disk', found[1]['path'].replace('/dev/', '')
        )
        if disk:
            await self.middleware.call('disk.swaps_configure')

        return True

    @item_method
    @accepts(Int('id'), Dict(
        'options',
        Str('label', required=True),
    ))
    async def remove(self, oid, options):
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
        pool = await self._get_instance(oid)

        verrors = ValidationErrors()

        found = self.__find_disk_from_topology(options['label'], pool)
        if not found:
            verrors.add('options.label', f'Label {options["label"]} not found on this pool.')

        if verrors:
            raise verrors

        await self.middleware.call('zfs.pool.remove', pool['name'], found[1]['guid'])

        await self.middleware.call('pool.sync_encrypted', oid)

        if found[1]['path'].endswith('.eli'):
            devname = found[1]['path'].replace('/dev/', '')[:-4]
            await self.middleware.call('disk.geli_detach_single', devname)

        disk = await self.middleware.call(
            'disk.label_to_disk', found[1]['path'].replace('/dev/', '')
        )
        if disk:
            await self.middleware.call('disk.swaps_remove_disks', [disk])
            await self.middleware.call('disk.unlabel', disk)

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
        pool = await self._get_instance(oid)

        verrors = await self.__common_encopt_validation(pool, options)

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

    async def __common_encopt_validation(self, pool, options):
        verrors = ValidationErrors()

        if pool['encrypt'] == 0:
            verrors.add('id', 'Pool is not encrypted.')

        # admin password is optional, its choice of the client to enforce
        # it or not.
        if 'admin_password' in options and not await self.middleware.call(
            'auth.check_user', 'root', options['admin_password']
        ):
            verrors.add('options.admin_password', 'Invalid admin password.')

        if verrors:
            raise verrors
        return verrors

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
        pool = await self._get_instance(oid)

        await self.__common_encopt_validation(pool, options)

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
        pool = await self._get_instance(oid)

        await self.__common_encopt_validation(pool, options)

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
        pool = await self._get_instance(oid)

        await self.__common_encopt_validation(pool, options)

        await self.middleware.call('disk.geli_recoverykey_rm', pool)

        return True

    @accepts()
    async def unlock_services_restart_choices(self):
        """
        Get a mapping of services identifiers and labels that can be restart
        on volume unlock.
        """
        svcs = {
            'afp': 'AFP',
            'cifs': 'SMB',
            'ftp': 'FTP',
            'iscsitarget': 'iSCSI',
            'nfs': 'NFS',
            'webdav': 'WebDAV',
            'jails': 'Jails/Plugins',
            'vms': 'Virtual Machines',
        }
        return svcs

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
        pool = await self._get_instance(oid)

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

        services_restart_choices = set((await self.unlock_services_restart_choices()).keys())
        options_services_restart = set(options['services_restart'])
        invalid_choices = options_services_restart - services_restart_choices
        if invalid_choices:
            verrors.add(
                'options.services_restart', f'Invalid choices: {", ".join(invalid_choices)}'
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
            [i] for i in options['services_restart'] + ['system_datasets', 'disk']
        ])
        if 'jails' in options['services_restart']:
            await self.middleware.call('core.bulk', 'jail.rc_action', [['RESTART']])
        if 'vms' in options['services_restart']:
            vms = (await self.middleware.call(
                'vm.query', [('autostart', '=', True)])
            )
            pool_name = pool['name']
            for vm in vms:
                for device in vm['devices']:
                    path = device['attributes'].get('path', '')
                    if f'/dev/zvol/{pool_name}/' in path or \
                            f'/mnt/{pool_name}/' in path:
                        await self.middleware.call('vm.stop', vm['id'])
                        await self.middleware.call('vm.start', vm['id'])

        await self.middleware.call_hook('pool.post_unlock', pool=pool)

        return True

    @item_method
    @accepts(Int('id'), Str('passphrase', private=True))
    @job(lock='lock_pool')
    async def lock(self, job, oid, passphrase):
        """
        Lock encrypted pool `id`.
        """
        pool = await self._get_instance(oid)

        verrors = ValidationErrors()

        if pool['encrypt'] == 0:
            verrors.add('id', 'Pool is not encrypted.')
        elif pool['status'] == 'OFFLINE':
            verrors.add('id', 'Pool already locked.')

        if not verrors:
            verrors.extend(await self.__pool_lock_pre_check(pool, passphrase))

        if verrors:
            raise verrors

        await self.middleware.call_hook('pool.pre_lock', pool=pool)

        sysds = await self.middleware.call('systemdataset.config')
        if sysds['pool'] == pool['name']:
            job = await self.middleware.call('systemdataset.update', {
                'pool': None, 'pool_exclude': pool['name'],
            })
            await job.wait()
            if job.error:
                raise CallError(job.error)

        await self.middleware.call('zfs.pool.export', pool['name'])

        for ed in await self.middleware.call(
                'datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]
        ):
            await self.middleware.call('disk.geli_detach_single', ed['encrypted_provider'])

        await self.middleware.call_hook('pool.post_lock', pool=pool)
        await self.middleware.call('service.restart', 'system_datasets')

        return True

    async def __pool_lock_pre_check(self, pool, passphrase):
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
    @accepts(Int('id'), Str('filename', default='geli.key'))
    async def download_encryption_key(self, oid, filename):
        """
        Download encryption key for a given pool `id`.
        """
        pool = await self.query([('id', '=', oid)], {'get': True})
        if not pool['encryptkey']:
            return None

        job_id, url = await self.middleware.call(
            'core.download',
            'filesystem.get',
            [os.path.join(self.GELI_KEYPATH, f"{pool['encryptkey']}.key")],
            filename,
        )
        return url

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
            resilver_delay = 0
            resilver_min_time_ms = 9000
            scan_idle = 0
        else:
            resilver_delay = 2
            resilver_min_time_ms = 3000
            scan_idle = 50

        sysctl.filter('vfs.zfs.resilver_delay')[0].value = resilver_delay
        sysctl.filter('vfs.zfs.resilver_min_time_ms')[0].value = resilver_min_time_ms
        sysctl.filter('vfs.zfs.scan_idle')[0].value = scan_idle

    @accepts()
    async def import_find(self):
        """
        Get a list of pools available for import with the following details:
        name, guid, status, hostname.
        """

        existing_guids = [i['guid'] for i in await self.middleware.call('pool.query')]

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
            yield entry

    @accepts(Dict(
        'pool_import',
        Str('guid', required=True),
        Str('name'),
        Str('passphrase', private=True),
        Bool('enable_attachments'),
    ))
    @job(lock='import_pool', pipes=['input'], check_pipes=False)
    async def import_pool(self, job, data):
        """
        Import a pool found with `pool.import_find`.

        If a `name` is specified the pool will be imported using that new name.

        `passphrase` is required while importing an encrypted pool. In that case this method needs to
        be called using /_upload/ endpoint with the encryption key.

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

        pool = None
        for p in await self.middleware.call('zfs.pool.find_import'):
            if p['guid'] == data['guid']:
                pool = p
                break
        if pool is None:
            raise CallError(f'Pool with guid "{data["guid"]}" not found', errno.ENOENT)

        try:
            job.check_pipe("input")
            key = job.pipes.input.r
        except ValueError:
            key = None

        passfile = None
        if key and data.get('passphrase'):
            encrypt = 2
            passfile = tempfile.mktemp(dir='/tmp/')
            with open(passfile, 'w') as f:
                os.chmod(passfile, 0o600)
                f.write(data['passphrase'])
        elif key:
            encrypt = 1
        else:
            encrypt = 0

        pool_name = data.get('name') or pool['name']
        pool_id = None
        try:
            pool_id = await self.middleware.call('datastore.insert', 'storage.volume', {
                'vol_name': pool_name,
                'vol_encrypt': encrypt,
                'vol_guid': data['guid'],
            })
            pool = await self.middleware.call('pool.query', [('id', '=', pool_id)], {'get': True})
            if encrypt > 0:
                if not os.path.exists(GELI_KEYPATH):
                    os.mkdir(GELI_KEYPATH)
                with open(pool['encryptkey_path'], 'wb') as f:
                    f.write(key.read())

            await self.middleware.call('pool.scrub.create', {
                'pool': pool_id,
            })

            await self.middleware.call('zfs.pool.import_pool', pool['guid'], {
                'altroot': '/mnt',
                'cachefile': ZPOOL_CACHE_FILE,
            })

            await self.middleware.call('zfs.dataset.update', pool_name, {
                'properties': {
                    'aclinherit': {'value': 'passthrough'},
                },
            })

            # Reset all mountpoints
            await self.middleware.call('zfs.dataset.inherit', pool_name, 'mountpoint', True)

            await self.middleware.call('pool.sync_encrypted', pool_id)
        except Exception:
            if pool_id:
                await self.middleware.call('datastore.delete', 'storage.volume', pool_id)
            if passfile:
                os.unlink(passfile)
            raise

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

        await self.middleware.call('service.reload', 'disk')
        await self.middleware.call_hook('pool.post_import_pool', pool)
        await self.middleware.call('pool.dataset.sync_db_keys', pool['name'])

        return True

    @accepts(
        Str('device'),
        Str('fs_type'),
        Dict('fs_options', additional_attrs=True),
        Str('dst_path')
    )
    @job(lock=lambda args: 'volume_import', logs=True)
    async def import_disk(self, job, device, fs_type, fs_options, dst_path):
        """
        Import a disk, by copying its content to a pool.

        .. examples(websocket)::

          Import a FAT32 (msdosfs) disk.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.import_disk,
                "params": [
                    "/dev/da0", "msdosfs", {}, "/mnt/tank/mydisk"
                ]
            }
        """
        job.set_progress(None, description="Mounting")

        src = os.path.join('/var/run/importcopy/tmpdir', os.path.relpath(device, '/'))

        if os.path.exists(src):
            os.rmdir(src)

        try:
            os.makedirs(src)

            async with KernelModuleContextManager({"ext2fs": "ext2fs",
                                                   "msdosfs": "msdosfs_iconv",
                                                   "ntfs": "fuse"}.get(fs_type)):
                async with MountFsContextManager(self.middleware, device, src, fs_type, fs_options, ["ro"]):
                    job.set_progress(None, description="Importing")

                    line = [
                        '/usr/local/bin/rsync',
                        '--info=progress2',
                        '--modify-window=1',
                        '-rltvh',
                        '--no-perms',
                        src + '/',
                        dst_path
                    ]
                    rsync_proc = await Popen(
                        line, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0, preexec_fn=os.setsid,
                    )
                    try:
                        progress_buffer = JobProgressBuffer(job)
                        while True:
                            line = await rsync_proc.stdout.readline()
                            job.logs_fd.write(line)
                            if line:
                                try:
                                    line = line.decode("utf-8", "ignore").strip()
                                    bits = re.split(r"\s+", line)
                                    if len(bits) == 6 and bits[1].endswith("%") and bits[1][:-1].isdigit():
                                        progress_buffer.set_progress(int(bits[1][:-1]))
                                    elif not line.endswith('/'):
                                        if (
                                            line not in ['sending incremental file list'] and
                                            'xfr#' not in line
                                        ):
                                            progress_buffer.set_progress(None, extra=line)
                                except Exception:
                                    logger.warning('Parsing error in rsync task', exc_info=True)
                            else:
                                break

                        progress_buffer.flush()
                        await rsync_proc.wait()
                        if rsync_proc.returncode != 0:
                            raise Exception("rsync failed with exit code %r" % rsync_proc.returncode)
                    except asyncio.CancelledError:
                        rsync_proc.kill()
                        raise

                    job.set_progress(100, description="Done", extra="")
        finally:
            os.rmdir(src)

    @accepts(Str("device"))
    def import_disk_autodetect_fs_type(self, device):
        """
        Autodetect filesystem type for `pool.import_disk`.

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.import_disk_autodetect_fs_type",
                "params": ["/dev/da0"]
            }
        """
        proc = subprocess.Popen(["blkid", device], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
        output = proc.communicate()[0].strip()

        if proc.returncode == 2:
            proc = subprocess.Popen(["file", "-s", device], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding="utf-8")
            output = proc.communicate()[0].strip()
            if proc.returncode != 0:
                raise CallError(f"blkid failed with code 2 and file failed with code {proc.returncode}: {output}")

            if "Unix Fast File system" in output:
                return "ufs"

            raise CallError(f"blkid failed with code 2 and file produced unexpected output: {output}")

        if proc.returncode != 0:
            raise CallError(f"blkid failed with code {proc.returncode}: {output}")

        m = re.search("TYPE=\"(.+?)\"", output)
        if m is None:
            raise CallError(f"blkid produced unexpected output: {output}")

        fs = {
            "ext2": "ext2fs",
            "ext3": "ext2fs",
            "ntfs": "ntfs",
            "vfat": "msdosfs",
        }.get(m.group(1))
        if fs is None:
            self.logger.info("Unknown FS: %s", m.group(1))
            return None

        return fs

    @accepts()
    def import_disk_msdosfs_locales(self):
        """
        Get a list of locales for msdosfs type to be used in `pool.import_disk`.
        """
        return [
            locale.strip()
            for locale in subprocess.check_output(["locale", "-a"], encoding="utf-8").split("\n")
            if locale.strip() and locale.strip() not in ["C", "POSIX"]
        ]

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
        """
        pool = await self._get_instance(oid)

        pool_count = await self.middleware.call('pool.query', [], {'count': True})
        is_freenas = await self.middleware.call('system.is_freenas')
        if (
            pool_count == 1 and not is_freenas and
            await self.middleware.call('failover.licensed') and
            not (await self.middleware.call('failover.config'))['disabled']
        ):
            raise CallError('Disable failover before exporting last pool on system.')

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
        disks = [i async for i in await self.middleware.call('pool.get_disks')]
        await self.middleware.call('disk.swaps_remove_disks', disks)

        sysds = await self.middleware.call('systemdataset.config')
        if sysds['pool'] == pool['name']:
            job.set_progress(40, 'Reconfiguring system dataset')
            sysds_job = await self.middleware.call('systemdataset.update', {
                'pool': None, 'pool_exclude': pool['name'],
            })
            await sysds_job.wait()
            if sysds_job.error:
                raise CallError(sysds_job.error)

        if pool['status'] == 'OFFLINE':
            # Pool exists only in database, its not imported
            pass
        elif options['destroy']:
            job.set_progress(60, 'Destroying pool')
            await self.middleware.call('zfs.pool.delete', pool['name'])

            job.set_progress(80, 'Cleaning disks')

            async def unlabel(disk):
                return await self.middleware.call('disk.unlabel', disk, False)
            await asyncio_map(unlabel, disks, limit=16)

            await self.middleware.call('disk.sync_all')

            await self.middleware.call('disk.geli_detach', pool, True)
            if pool['encrypt'] > 0:
                try:
                    os.remove(pool['encryptkey_path'])
                except OSError as e:
                    self.logger.warn(
                        'Failed to remove encryption key %s: %s',
                        pool['encryptkey_path'],
                        e,
                        exc_info=True,
                    )
        else:
            job.set_progress(80, 'Exporting pool')
            await self.middleware.call('zfs.pool.export', pool['name'])
            await self.middleware.call('disk.geli_detach', pool)

        job.set_progress(90, 'Cleaning up')
        if os.path.isdir(pool['path']):
            try:
                # We dont try to remove recursively to avoid removing files that were
                # potentially hidden by the mount
                os.rmdir(pool['path'])
            except OSError as e:
                self.logger.warn('Failed to remove pointoint %s: %s', pool['path'], e)

        await self.middleware.call('datastore.delete', 'storage.volume', oid)
        await self.middleware.call(
            'datastore.delete', PoolDatasetService.dataset_store,
            [['OR', [['name', '=', pool['name']], ['name', '^', f'{pool["name"]}/']]]],
        )

        # scrub needs to be regenerated in crontab
        await self.middleware.call('service.restart', 'cron')

        await self.middleware.call_hook('pool.post_export', pool=pool, options=options)

    @item_method
    @accepts(
        Int('id'),
        Dict(
            'options',
            Dict(
                'geli',
                Str('passphrase', private=True, default=''),
            ),
        )
    )
    @job(lock='pool_expand')
    async def expand(self, job, id, options):
        """
        Expand pool to fit all available disk space.
        """

        pool = await self._get_instance(id)

        if pool['encrypt']:
            if not pool['is_decrypted']:
                raise CallError('You can only expand decrypted pool')

            for error in (await self.__pool_lock_pre_check(pool, options['geli']['passphrase'])).errors:
                raise CallError(error.errmsg)

        await self.middleware.run_in_thread(bsd.geom.scan)

        try:
            sysctl.filter('kern.geom.debugflags')[0].value = 16

            geli_resize = []
            try:
                for vdev in sum(pool['topology'].values(), []):
                    if vdev['type'] != 'DISK':
                        logger.debug('Not expanding vdev of type %r', vdev['type'])
                        continue

                    if vdev['status'] != 'ONLINE':
                        logger.debug('Not expanding vdev that is %r', vdev['status'])
                        continue

                    partition_number = RE_DISKPART.match(vdev['device'])
                    if partition_number is None:
                        logger.debug('Could not parse partition number from %r', vdev['device'])
                        continue

                    assert partition_number.group(1) == vdev['disk']
                    partition_number = int(partition_number.group(2)[1:])

                    mediasize = bsd.geom.geom_by_name('LABEL', vdev['device']).provider.mediasize

                    await run('camcontrol', 'reprobe', vdev['disk'])
                    await run('gpart', 'recover', vdev['disk'])
                    await run('gpart', 'resize', '-i', str(partition_number), vdev['disk'])

                    if pool['encrypt']:
                        geli_resize_cmd = (
                            'geli', 'resize', '-s', str(mediasize), vdev['device']
                        )
                        rollback_cmd = (
                            'gpart', 'resize', '-i', str(partition_number), '-s', str(mediasize), vdev['disk']
                        )

                        logger.warning('It will be obligatory to notify GELI that the provider has been resized: %r',
                                       join_commandline(geli_resize_cmd))
                        logger.warning('Or to resize provider back: %r',
                                       join_commandline(rollback_cmd))

                        geli_resize.append((geli_resize_cmd, rollback_cmd))
            finally:
                if geli_resize:
                    failed_rollback = []

                    lock_job = await self.middleware.call('pool.lock', pool['id'], options['geli']['passphrase'])
                    await lock_job.wait()
                    if lock_job.error:
                        logger.warning('Error locking pool: %s', lock_job.error)

                        for geli_resize_cmd, rollback_cmd in geli_resize:
                            if not await self.__run_rollback_cmd(rollback_cmd):
                                failed_rollback.append(rollback_cmd)

                        if failed_rollback:
                            raise CallError('Locking your encrypted pool failed and rolling back changes failed too. '
                                            'You\'ll need to run the following commands manually:\n%s',
                                            '\n'.join(map(join_commandline, failed_rollback)))
                    else:
                        for geli_resize_cmd, rollback_cmd in geli_resize:
                            try:
                                await run(*geli_resize_cmd, encoding='utf-8', errors='ignore')
                            except subprocess.CalledProcessError as geli_resize_error:
                                if geli_resize_error.stderr.strip() == 'geli: Size hasn\'t changed.':
                                    logger.info('%s: %s',
                                                join_commandline(geli_resize_cmd),
                                                geli_resize_error.stderr.strip())
                                else:
                                    logger.error('%r failed: %s. Resizing partition back',
                                                 join_commandline(geli_resize_cmd),
                                                 geli_resize_error.stderr.strip())
                                    if not await self.__run_rollback_cmd(rollback_cmd):
                                        failed_rollback.append(rollback_cmd)

                        if failed_rollback:
                            raise CallError('Resizing partitions of your encrypted pool failed and rolling back '
                                            'changes failed too. You\'ll need to run the following commands manually:\n'
                                            '%s',
                                            '\n'.join(map(join_commandline, failed_rollback)))

                        if options['geli']['passphrase']:
                            unlock_job = await self.middleware.call('pool.unlock', pool['id'],
                                                                    {'passphrase': options['geli']['passphrase']})
                        else:
                            unlock_job = await self.middleware.call('pool.unlock', pool['id'],
                                                                    {'recoverykey': True},
                                                                    pipes=Pipes(input=self.middleware.pipe()))

                            def copy():
                                with open(pool['encryptkey_path'], 'rb') as f:
                                    shutil.copyfileobj(f, unlock_job.pipes.input.w)

                            try:
                                await self.middleware.run_in_thread(copy)
                            finally:
                                await self.middleware.run_in_thread(unlock_job.pipes.input.w.close)

                        await unlock_job.wait()
                        if unlock_job.error:
                            raise CallError(unlock_job.error)
        finally:
            sysctl.filter('kern.geom.debugflags')[0].value = 0

        for vdev in sum(pool['topology'].values(), []):
            if vdev['type'] != 'DISK':
                continue

            if vdev['status'] != 'ONLINE':
                continue

            await self.middleware.call('zfs.pool.online', pool['name'], vdev['guid'])

    async def __run_rollback_cmd(self, rollback_cmd):
        try:
            await run(*rollback_cmd, encoding='utf-8', errors='ignore')
        except subprocess.CalledProcessError as rollback_error:
            logger.critical(
                '%r failed: %s. To restore your pool functionality you will have to run this command manually.',
                join_commandline(rollback_cmd),
                rollback_error.stderr.strip()
            )
            return False
        else:
            return True

    @item_method
    @accepts(Int('id'))
    async def attachments(self, oid):
        """
        Return a list of services dependent of this pool.

        Responsible for telling the user whether there is a related
        share, asking for confirmation.
        """
        pool = await self._get_instance(oid)
        return await self.middleware.call('pool.dataset.attachments', pool['name'])

    @item_method
    @accepts(Int('id'))
    async def processes(self, oid):
        """
        Returns a list of running processes using this pool.
        """
        pool = await self._get_instance(oid)
        return await self.middleware.call('pool.dataset.processes', pool['name'])

    @staticmethod
    def __get_dev_and_disk(topology):
        rv = []
        for values in topology.values():
            values = values.copy()
            while values:
                value = values.pop()
                if value['type'] == 'DISK':
                    rv.append((value['path'].replace('/dev/', ''), value['disk']))
                values += value.get('children') or []
        return rv

    @private
    def sync_encrypted(self, pool=None):
        """
        This syncs the EncryptedDisk table with the current state
        of a volume
        """
        if pool is not None:
            filters = [('id', '=', pool)]
        else:
            filters = []

        pools = self.middleware.call_sync('pool.query', filters)
        if not pools:
            return

        # Grab all disks at once to avoid querying every iteration
        disks = {i['devname']: i['identifier'] for i in self.middleware.call_sync('disk.query')}

        for pool in pools:
            if not pool['is_decrypted'] or pool['status'] == 'OFFLINE' or pool['encrypt'] == 0:
                continue

            provs = []
            for dev, disk in self.__get_dev_and_disk(pool['topology']):
                if not dev.endswith(".eli"):
                    continue
                prov = dev[:-4]
                diskid = disks.get(disk)
                ed = self.middleware.call_sync('datastore.query', 'storage.encrypteddisk', [
                    ('encrypted_provider', '=', prov)
                ])
                if not ed:
                    if not diskid:
                        self.logger.warn('Could not find Disk entry for %s', disk)
                    self.middleware.call_sync('datastore.insert', 'storage.encrypteddisk', {
                        'encrypted_volume': pool['id'],
                        'encrypted_provider': prov,
                        'encrypted_disk': diskid,
                    })
                elif diskid and ed[0]['encrypted_disk'] != diskid:
                    self.middleware.call_sync(
                        'datastore.update', 'storage.encrypteddisk', ed[0]['id'],
                        {'encrypted_disk': diskid},
                    )
                provs.append(prov)

            # Delete devices no longer in pool from database
            self.middleware.call_sync('datastore.delete', 'storage.encrypteddisk', [
                ('encrypted_volume', '=', pool['id']), ('encrypted_provider', 'nin', provs)
            ])

    def __dtrace_read(self, job, proc):
        while True:
            read = proc.stdout.readline()
            if read == b'':
                break
            read = read.decode(errors='ignore').strip()
            job.set_progress(None, read)

    @private
    @job()
    def import_on_boot(self, job):
        cachedir = os.path.dirname(ZPOOL_CACHE_FILE)
        if not os.path.exists(cachedir):
            os.mkdir(cachedir)

        if (
            not self.middleware.call_sync('system.is_freenas') and
            self.middleware.call_sync('failover.licensed')
        ):
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

        try:
            proc = subprocess.Popen(
                ['dtrace', '-qn', 'zfs-dbgmsg{printf("%s\\n", stringof(arg0))}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

            start_daemon_thread(target=self.__dtrace_read, args=[job, proc])

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
                    self.logger.warn(
                        'Failed to set cache file for %s', pool['name'], exc_info=True,
                    )

                try:
                    if os.path.isdir('/mnt/mnt'):
                        # Reset all mountpoints
                        self.middleware.call_sync(
                            'zfs.dataset.inherit', pool['name'], 'mountpoint', True
                        )
                except Exception:
                    self.logger.warn(
                        'Failed to inherit mountpoints for %s', pool['name'], exc_info=True,
                    )

                unlock_job = self.middleware.call_sync(
                    'pool.dataset.unlock', pool['name'], {'toggle_attachments': False, 'recursive': True}
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
                if self.middleware.call_sync('pool.dataset._get_instance', pool['name'])['locked']:
                    with contextlib.suppress(CallError):
                        self.middleware.call_sync('zfs.dataset.umount', pool['name'], {'force': True})

        finally:
            proc.kill()
            proc.wait()

        with contextlib.suppress(OSError):
            os.unlink(ZPOOL_KILLCACHE)

        if os.path.exists(ZPOOL_CACHE_FILE):
            shutil.copy(ZPOOL_CACHE_FILE, zpool_cache_saved)

        # Now that pools have been imported we are ready to configure system dataset,
        # collectd and syslogd which may depend on them.
        try:
            self.middleware.call_sync('etc.generate', 'system_dataset')
        except Exception:
            self.logger.warn('Failed to setup system dataset', exc_info=True)

        try:
            self.middleware.call_sync('etc.generate', 'collectd')
        except Exception:
            self.logger.warn('Failed to configure collectd', exc_info=True)

        try:
            self.middleware.call_sync('etc.generate', 'syslogd')
        except Exception:
            self.logger.warn('Failed to configure syslogd', exc_info=True)

        try:
            self.middleware.call_sync('etc.generate', 'zerotier')
        except Exception:
            self.logger.warn('Failed to configure zerotier', exc_info=True)

        # Configure swaps after importing pools. devd events are not yet ready at this
        # stage of the boot process.
        self.middleware.run_coroutine(self.middleware.call('disk.swaps_configure'), wait=False)

        job.set_progress(100, 'Pools import completed')

    """
    These methods are hacks for old UI which supports only one volume import at a time
    """

    dismissed_import_disk_jobs = set()

    @private
    async def get_current_import_disk_job(self):
        import_jobs = await self.middleware.call('core.get_jobs', [('method', '=', 'pool.import_disk')])
        not_dismissed_import_jobs = [job for job in import_jobs if job["id"] not in self.dismissed_import_disk_jobs]
        if not_dismissed_import_jobs:
            return not_dismissed_import_jobs[0]

    @private
    async def dismiss_current_import_disk_job(self):
        current_import_job = await self.get_current_import_disk_job()
        if current_import_job:
            self.dismissed_import_disk_jobs.add(current_import_job["id"])


class PoolDatasetUserPropService(CRUDService):

    class Config:
        namespace = 'pool.dataset.userprop'

    @filterable
    def query(self, filters=None, options=None):
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
                Str('value',required=True),
            )
        )
    )
    async def do_create(self, data):
        """
        Create a user property for a given `id` dataset.
        """
        dataset = await self._get_instance(data['id'])
        verrors = await self.__common_validation(dataset, data['property'], 'dataset_user_prop_create')
        verrors.check()

        await self.middleware.call(
            'zfs.dataset.update', data['id'], {
                'properties': {data['property']['name']: {'value': data['property']['value']}}
            }
        )

        return await self._get_instance(data['id'])

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
        dataset = await self._get_instance(id)
        verrors = await self.__common_validation(dataset, data, 'dataset_user_prop_update', True)
        verrors.check()

        await self.middleware.call(
            'zfs.dataset.update', id, {
                'properties': {data['name']: {'value': data['value']}}
            }
        )

        return await self._get_instance(id)

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
        dataset = await self._get_instance(id)
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
    encryption_key = sa.Column(sa.Text(), nullable=True)


class PoolDatasetService(CRUDService):

    attachment_delegates = []
    dataset_store = 'storage.encrypteddataset'

    class Config:
        namespace = 'pool.dataset'

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

        data['encryption_key'] = await self.middleware.call('pwenc.encrypt', data['encryption_key'])

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

        return pk

    @private
    def encrypted_roots_query_db(self, filters=None, decrypt=False):
        return {
            d['name']: d['encryption_key'] if not decrypt else self.middleware.call_sync(
                'pwenc.decrypt', d['encryption_key']
            )
            for d in self.middleware.call_sync('datastore.query', self.dataset_store, filters or [])
        }

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
        db_results = self.encrypted_roots_query_db([['OR', [['name', '=', name], ['name', '^', f'{name}/']]]], True)

        def normalize(ds):
            passphrase = ZFSKeyFormat(ds['key_format']['value']) == ZFSKeyFormat.PASSPHRASE
            key = db_results.get(ds['name']) if not passphrase else None
            return ds['name'], {'encryption_key': key, **ds}

        def check_key(ds):
            return options.get('all') or (ds['key_loaded'] and key_loaded) or (not ds['key_loaded'] and not key_loaded)

        return dict(map(
            normalize,
            filter(
                lambda d: d['name'] == d['encryption_root'] and d['encrypted']
                and f'{d["name"]}/'.startswith(f'{name}/') and check_key(d),
                self.query()
            )
        ))

    @periodic(86400)
    @private
    @job(lock=lambda args: f'sync_encrypted_pool_dataset_keys_{args}')
    def sync_db_keys(self, job, name=None):
        filters = [['OR', [['name', '=', name], ['name', '^', f'{name}/']]]] if name else []
        db_datasets = self.encrypted_roots_query_db(filters, True)
        encrypted_roots = {d['name']: d for d in self.query(filters) if d['name'] == d['encryption_root']}
        to_remove = []
        check_key_job = self.middleware.call_sync('zfs.dataset.bulk_process', 'check_key', [
            (name, {'key': db_datasets[name]}) for name in db_datasets
        ])
        check_key_job.wait_sync()
        if check_key_job.error:
            self.middleware.logger.error(f'Failed to sync database keys: {check_key_job.error}')
            return

        for dataset, status in zip(db_datasets, check_key_job.result):
            if not status['result']:
                to_remove.append(dataset)
            elif status['error']:
                if dataset not in encrypted_roots:
                    to_remove.append(dataset)
                else:
                    self.middleware.logger.error(f'Failed to check encryption status for {dataset}: {status["error"]}')

        self.middleware.call_sync('datastore.delete', self.dataset_store, [['name', 'in', to_remove]])

    @accepts(Str('id'))
    @job(lock='dataset_export_keys', pipes=['output'])
    def export_keys(self, job, id):
        """
        Export keys for `id` and its children which are stored in the system. The exported file is a JSON file
        which has a dictionary containing dataset names as keys and their keys as the value.

        Please refer to websocket documentation for downloading the file.
        """
        self.middleware.call_sync('pool.dataset._get_instance', id)
        sync_job = self.middleware.call_sync('pool.dataset.sync_db_keys', id)
        sync_job.wait_sync()

        datasets = self.encrypted_roots_query_db(
            [['OR', [['name', '=', id], ['name', '^', f'{id}/']]]], decrypt=True
        )
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                temp_path = f.name
                os.chmod(temp_path, 0o600)
                f.write(json.dumps(datasets))

            with open(temp_path, 'rb') as f:
                shutil.copyfileobj(f, job.pipes.output.w)
        finally:
            if os.path.exists(temp_path or ''):
                os.unlink(temp_path)

    @accepts(
        Str('id'),
        Dict(
            'lock_options',
            Bool('force_umount', default=False),
        )
    )
    async def lock(self, id, options):
        """
        Locks `id` dataset. It will unmount the dataset and its children before locking.
        """
        ds = await self._get_instance(id)

        if not ds['encrypted']:
            raise CallError(f'{id} is not encrypted')
        elif ds['locked']:
            raise CallError(f'Dataset {id} is already locked')
        elif ZFSKeyFormat(ds['key_format']['value']) != ZFSKeyFormat.PASSPHRASE:
            raise CallError('Only datasets which are encrypted with passphrase can be locked')
        elif id != ds['encryption_root']:
            raise CallError(f'Please lock {ds["encryption_root"]}. Only encryption roots can be locked.')
        elif id == (await self.middleware.call('systemdataset.config'))['pool']:
            raise CallError(f'Please move system dataset to another pool before locking {id}')

        await self.middleware.call(
            'zfs.dataset.unload_key', id, {'umount': True, 'force_umount': options['force_umount'], 'recursive': True}
        )

        return True

    @accepts(
        Str('id'),
        Dict(
            'unlock_options',
            Bool('key_file', default=False),
            Bool('toggle_attachments', default=True),
            Bool('recursive', default=False),
            List(
                'datasets', items=[
                    Dict(
                        'dataset',
                        Str('name', required=True, empty=False),
                        Str('key', validators=[Range(min=64, max=64)], private=True),
                        Str('passphrase', empty=False, private=True),
                    )
                ], default=[],
            ),
        )
    )
    @job(lock=lambda args: f'dataset_unlock_{args[0]}', pipes=['input'], check_pipes=False)
    def unlock(self, job, id, options):
        """
        Unlock `id` dataset.

        If `id` dataset is not encrypted an exception will be raised. There is one exception:
        when `id` is a root dataset and `unlock_options.recursive` is specified, encryption
        validation will not be performed for `id`. This allow unlocking encrypted children the `id` pool.

        For datasets which are encrypted with a passphrase, include the passphrase with
        `unlock_options.datasets`.

        Uploading a json file which contains encrypted dataset keys can be specified with
        `unlock_options.key_file`. The format is similar to that used for exporting encrypted dataset keys.
        """
        verrors = ValidationErrors()
        dataset = self.middleware.call_sync('pool.dataset._get_instance', id)
        keys_supplied = {}

        if options['key_file']:
            keys_supplied = self._retrieve_keys_from_file(job)

        for i, ds in enumerate(options['datasets']):
            if all(ds.get(k) for k in ('key', 'passphrase')):
                verrors.add(
                    f'unlock_options.datasets.{i}.dataset.key',
                    f'Must not be specified when passphrase for {ds["name"]} is supplied'
                )
            keys_supplied[ds['name']] = ds.get('key') or ds.get('passphrase')

        if '/' in id or not options['recursive']:
            if not dataset['locked']:
                verrors.add('id', f'{id} dataset is not locked')
            elif dataset['encryption_root'] != id:
                verrors.add('id', 'Only encryption roots can be unlocked')
            else:
                if not bool(self.encrypted_roots_query_db([['name', '=', id]])) and id not in keys_supplied:
                    verrors.add('unlock_options.datasets', f'Please specify key for {id}')

        verrors.check()

        locked_datasets = []
        datasets = self.query_encrypted_datasets(id.split('/', 1)[0], {'key_loaded': False})
        for name, ds in datasets.items():
            ds_key = keys_supplied.get(name) or ds['encryption_key']
            if ds['locked'] and id != name and id.startswith(name):
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
        for name in sorted(
            filter(
                lambda n: n and f'{n}/'.startswith(f'{id}/') and datasets[n]['locked'],
                (datasets if options['recursive'] else [id])
            ),
            key=lambda v: v.count('/')
        ):
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

            try:
                self.middleware.call_sync(
                    'zfs.dataset.load_key', name, {'key': datasets[name]['key'], 'mount': True, 'recursive': True}
                )
            except CallError as e:
                failed[name]['error'] = 'Invalid Key' if 'incorrect key provided' in str(e).lower() else str(e)
            else:
                unlocked.append(name)

        if options['toggle_attachments'] and not failed:
            j = self.middleware.call_sync('pool.dataset.toggle_attachments', self.__attachments_path(dataset))
            j.wait_sync()

        if unlocked:
            for unlocked_dataset in filter(lambda d: d in keys_supplied, unlocked):
                self.middleware.call_sync(
                    'pool.dataset.insert_or_update_encrypted_record', {
                        'encryption_key': keys_supplied[unlocked_dataset], 'name': unlocked_dataset,
                        'key_format': datasets[unlocked_dataset]['key_format']['value'],
                    }
                )

        return {'unlocked': unlocked, 'failed': failed}

    @private
    @job(lock=lambda args: f'toggle_attachments_{args[0]}')
    async def toggle_attachments(self, job, path):
        for delegate in self.attachment_delegates:
            if delegate.name in ('jail', 'vm'):
                await delegate.toggle((await delegate.query(path, False)), True)
            else:
                await delegate.toggle([], True)

    @accepts(
        Str('id'),
        Dict(
            'encryption_root_summary_options',
            Bool('key_file', default=False),
            List(
                'datasets', items=[
                    Dict(
                        'dataset',
                        Str('name', required=True, empty=False),
                        Str('key', validators=[Range(min=64, max=64)], private=True),
                        Str('passphrase', empty=False, private=True),
                    )
                ], default=[],
            ),
        )
    )
    @job(lock=lambda args: f'encryption_summary_options_{args[0]}', pipes=['input'], check_pipes=False)
    def encryption_summary(self, job, id, options):
        """
        Retrieve summary of all encrypted roots under `id`.

        Keys/passphrase can be supplied to check if the keys are valid.

        Example output:
        [
            {
                "name": "hex",
                "key_format": "HEX",
                "key_present": true,
                "valid_key": true,
                "locked": false
            },
            {
                "name": "hex/p",
                "key_format": "PASSPHRASE",
                "key_present": false,
                "valid_key": false,
                "locked": true
            }
        ]
        """
        keys_supplied = {}
        verrors = ValidationErrors()
        if options['key_file']:
            keys_supplied = self._retrieve_keys_from_file(job)

        for i, ds in enumerate(options['datasets']):
            if all(ds.get(k) for k in ('key', 'passphrase')):
                verrors.add(
                    f'unlock_options.datasets.{i}.dataset.key',
                    f'Must not be specified when passphrase for {ds["name"]} is supplied'
                )
            keys_supplied[ds['name']] = ds.get('key') or ds.get('passphrase')

        verrors.check()
        datasets = self.query_encrypted_datasets(id, {'all': True})

        to_check = []
        for name, ds in datasets.items():
            ds_key = keys_supplied.get(name) or ds['encryption_key']
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
                'name': ds_name, 'key_format': ZFSKeyFormat(data['key_format']['value']).value,
                'key_present_in_database': bool(data['encryption_key']),
                'valid_key': bool(status['result']), 'locked': data['locked']
            })

        return results

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
    @job(lock=lambda args: f'dataset_change_key_{args[0]}', pipes=['input'], check_pipes=False)
    async def change_key(self, job, id, options):
        """
        Change encryption properties for `id` encrypted dataset.

        Changing dataset encryption to use passphrase instead of a key is not allowed if:

        1) It has encrypted roots as children which are encrypted with a key
        2) If it is a root dataset where the system dataset is located
        """
        ds = await self._get_instance(id)
        verrors = ValidationErrors()
        if not ds['encrypted']:
            verrors.add('id', 'Dataset is not encrypted')
        elif ds['locked']:
            verrors.add('id', 'Dataset must be unlocked before key can be changed')

        if not verrors and options['passphrase']:
            if any(
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
        await self.insert_or_update_encrypted_record(
            {'encryption_key': key, 'key_format': 'PASSPHRASE' if options['passphrase'] else 'HEX', 'name': id}
        )
        if options['passphrase'] and ZFSKeyFormat(ds['key_format']['value']) != ZFSKeyFormat.PASSPHRASE:
            await self.middleware.call('pool.dataset.sync_db_keys', id)

    @accepts(Str('id'))
    async def inherit_parent_encryption_properties(self, id):
        """
        Allows inheriting parent's encryption root discarding its current encryption settings. This
        can only be done where `id` has an encrypted parent and `id` itself is an encryption root.
        """
        ds = await self._get_instance(id)
        if not ds['encrypted']:
            raise CallError(f'Dataset {id} is not encrypted')
        elif ds['encryption_root'] != id:
            raise CallError(f'Dataset {id} is not an encryption root')
        elif ds['locked']:
            raise CallError('Dataset must be unlocked to perform this operation')
        elif '/' not in id:
            raise CallError('Root datasets do not have a parent and cannot inherit encryption settings')
        else:
            parent = await self._get_instance(id.rsplit('/', 1)[0])
            if not parent['encrypted']:
                raise CallError('This operation requires the parent dataset to be encrypted')
            else:
                parent_encrypted_root = await self._get_instance(parent['encryption_root'])
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

    @private
    def _retrieve_keys_from_file(self, job):
        job.check_pipe('input')
        try:
            data = json.loads(job.pipes.input.r.read(10240))
        except json.JSONDecodeError:
            raise CallError('Input file must be a valid JSON file')

        if not isinstance(data, dict) or any(not isinstance(v, str) for v in data.values()):
            raise CallError('Please specify correct format for input file')

        return data

    @filterable
    def query(self, filters=None, options=None):
        """
        Query Pool Datasets with `query-filters` and `query-options`.
        """
        # Optimization for cases in which they can be filtered at zfs.dataset.query
        zfsfilters = []
        for f in filters or []:
            if len(f) == 3:
                if f[0] in ('id', 'name', 'pool', 'type'):
                    zfsfilters.append(f)

        return filter_list(
            self.__transform(self.middleware.call_sync('zfs.dataset.query', zfsfilters)), filters, options
        )

    def __transform(self, datasets):
        """
        We need to transform the data zfs gives us to make it consistent/user-friendly,
        making it match whatever pool.dataset.{create,update} uses as input.
        """
        def transform(dataset):
            for orig_name, new_name, method in (
                ('org.freenas:description', 'comments', None),
                ('org.freenas:quota_warning', 'quota_warning', None),
                ('org.freenas:quota_critical', 'quota_critical', None),
                ('org.freenas:refquota_warning', 'refquota_warning', None),
                ('org.freenas:refquota_critical', 'refquota_critical', None),
                ('dedup', 'deduplication', str.upper),
                ('aclmode', None, str.upper),
                ('atime', None, str.upper),
                ('casesensitivity', None, str.upper),
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
            ):
                if orig_name not in dataset['properties']:
                    continue
                i = new_name or orig_name
                dataset[i] = dataset['properties'][orig_name]
                if method:
                    dataset[i]['value'] = method(dataset[i]['value'])
            del dataset['properties']

            dataset['locked'] = dataset['encrypted'] and not dataset['key_loaded']

            rv = []
            for child in dataset['children']:
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
            '512', '1K', '2K', '4K', '8K', '16K', '32K', '64K', '128K',
        ]),
        Bool('sparse'),
        Bool('force_size'),
        Str('comments'),
        Str('sync', enum=[
            'STANDARD', 'ALWAYS', 'DISABLED',
        ]),
        Str('compression', enum=[
            'OFF', 'LZ4', 'GZIP', 'GZIP-1', 'GZIP-9', 'ZLE', 'LZJB',
        ]),
        Str('atime', enum=['ON', 'OFF']),
        Str('exec', enum=['ON', 'OFF']),
        Int('quota', null=True),
        Int('quota_warning', validators=[Range(0, 100)]),
        Int('quota_critical', validators=[Range(0, 100)]),
        Int('refquota', null=True),
        Int('refquota_warning', validators=[Range(0, 100)]),
        Int('refquota_critical', validators=[Range(0, 100)]),
        Int('reservation'),
        Int('refreservation'),
        Int('copies'),
        Str('snapdir', enum=['VISIBLE', 'HIDDEN']),
        Str('deduplication', enum=['ON', 'VERIFY', 'OFF']),
        Str('readonly', enum=['ON', 'OFF']),
        Str('recordsize', enum=[
            '512', '1K', '2K', '4K', '8K', '16K', '32K', '64K', '128K', '256K', '512K', '1024K',
        ]),
        Str('casesensitivity', enum=['SENSITIVE', 'INSENSITIVE', 'MIXED']),
        Str('aclmode', enum=['PASSTHROUGH', 'RESTRICTED']),
        Str('share_type', default='GENERIC', enum=['GENERIC', 'SMB']),
        Ref('encryption_options'),
        Bool('encryption', default=False),
        Bool('inherit_encryption', default=True),
        register=True,
    ))
    async def do_create(self, data):
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
        else:
            await self.__common_validation(verrors, 'pool_dataset_create', data, 'CREATE')

        mountpoint = os.path.join('/mnt', data['name'])
        if os.path.exists(mountpoint):
            verrors.add('pool_dataset_create.name', f'Path {mountpoint} already exists')

        if data['share_type'] == 'SMB':
            data['casesensitivity'] = 'INSENSITIVE'
            data['aclmode'] = 'RESTRICTED'

        if (await self._get_instance(data['name'].rsplit('/', 1)[0]))['locked']:
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
                parent_encryption_root = (await self._get_instance(data['name'].rsplit('/', 1)[0]))['encryption_root']
                if (
                    parent_encryption_root and ZFSKeyFormat(
                        (await self._get_instance(parent_encryption_root))['key_format']['value']
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

        if verrors:
            raise verrors

        props = {}
        for i, real_name, transform in (
            ('aclmode', None, str.lower),
            ('atime', None, str.lower),
            ('casesensitivity', None, str.lower),
            ('comments', 'org.freenas:description', None),
            ('compression', None, str.lower),
            ('copies', None, lambda x: str(x)),
            ('deduplication', 'dedup', str.lower),
            ('exec', None, str.lower),
            ('quota', None, _none),
            ('quota_warning', 'org.freenas:quota_warning', str),
            ('quota_critical', 'org.freenas:quota_critical', str),
            ('readonly', None, str.lower),
            ('recordsize', None, None),
            ('refquota', None, _none),
            ('refquota_warning', 'org.freenas:refquota_warning', str),
            ('refquota_critical', 'org.freenas:refquota_critical', str),
            ('refreservation', None, _none),
            ('reservation', None, _none),
            ('snapdir', None, str.lower),
            ('sparse', None, None),
            ('sync', None, str.lower),
            ('volblocksize', None, None),
            ('volsize', None, lambda x: str(x)),
        ):
            if i not in data:
                continue
            name = real_name or i
            props[name] = data[i] if not transform else transform(data[i])

        props.update(encryption_dict)

        await self.middleware.call('zfs.dataset.create', {
            'name': data['name'],
            'type': data['type'],
            'properties': props,
        })

        await self.insert_or_update_encrypted_record({
            'name': data['name'], 'encryption_key': encryption_dict.get('key'),
            'key_format': encryption_dict.get('keyformat')
        })

        data['id'] = data['name']

        await self.middleware.call('zfs.dataset.mount', data['name'])

        if data['type'] == 'FILESYSTEM' and data['share_type'] == 'SMB':
            await self.middleware.call('pool.dataset.permission', data['id'], {'mode': None})

        return await self._get_instance(data['id'])

    def _add_inherit(name):
        def add(attr):
            attr.enum.append('INHERIT')
        return {'name': name, 'method': add}

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
        ('edit', _add_inherit('atime')),
        ('edit', _add_inherit('exec')),
        ('edit', _add_inherit('sync')),
        ('edit', _add_inherit('compression')),
        ('edit', _add_inherit('deduplication')),
        ('edit', _add_inherit('readonly')),
        ('edit', _add_inherit('recordsize')),
        ('edit', _add_inherit('snapdir')),
        ('add', Inheritable('quota_warning', value=Int('quota_warning', validators=[Range(0, 100)]))),
        ('add', Inheritable('quota_critical', value=Int('quota_critical', validators=[Range(0, 100)]))),
        ('add', Inheritable('refquota_warning', value=Int('refquota_warning', validators=[Range(0, 100)]))),
        ('add', Inheritable('refquota_critical', value=Int('refquota_critical', validators=[Range(0, 100)]))),
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

        dataset = await self.middleware.call('pool.dataset.query', [('id', '=', id)])
        if not dataset:
            verrors.add('id', f'{id} does not exist', errno.ENOENT)
        else:
            data['type'] = dataset[0]['type']
            data['name'] = dataset[0]['name']
            if data['type'] == 'VOLUME':
                data['volblocksize'] = dataset[0]['volblocksize']['value']
            await self.__common_validation(verrors, 'pool_dataset_update', data, 'UPDATE')
            if 'volsize' in data:
                if data['volsize'] < dataset[0]['volsize']['parsed']:
                    verrors.add('pool_dataset_update.volsize',
                                'You cannot shrink a zvol from GUI, this may lead to data loss.')
        if verrors:
            raise verrors

        properties_definitions = (
            ('aclmode', None, str.lower, True),
            ('atime', None, str.lower, True),
            ('comments', 'org.freenas:description', None, False),
            ('sync', None, str.lower, True),
            ('compression', None, str.lower, True),
            ('deduplication', 'dedup', str.lower, True),
            ('exec', None, str.lower, True),
            ('quota', None, _none, False),
            ('quota_warning', 'org.freenas:quota_warning', str, True),
            ('quota_critical', 'org.freenas:quota_critical', str, True),
            ('refquota', None, _none, False),
            ('refquota_warning', 'org.freenas:refquota_warning', str, True),
            ('refquota_critical', 'org.freenas:refquota_critical', str, True),
            ('reservation', None, _none, False),
            ('refreservation', None, _none, False),
            ('copies', None, None, False),
            ('snapdir', None, str.lower, True),
            ('readonly', None, str.lower, True),
            ('recordsize', None, None, True),
            ('volsize', None, lambda x: str(x), False),
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

        try:
            rv = await self.middleware.call('zfs.dataset.update', id, {'properties': props})
        except ZFSSetPropertyError as e:
            verrors = ValidationErrors()
            verrors.add_child('pool_dataset_update', self.__handle_zfs_set_property_error(e, properties_definitions))
            raise verrors

        if data['type'] == 'VOLUME' and 'volsize' in data:
            if await self.middleware.call('iscsi.extent.query', [('path', '=', f'zvol/{id}')]):
                await self._service_change('iscsitarget', 'reload')

        return rv

    async def __common_validation(self, verrors, schema, data, mode):
        assert mode in ('CREATE', 'UPDATE')

        parent = await self.middleware.call(
            'zfs.dataset.query',
            [('id', '=', data['name'].rsplit('/')[0])]
        )

        if not parent:
            verrors.add(
                f'{schema}.name',
                'Please specify a pool which exists for the dataset/volume to be created'
            )
        else:
            parent = parent[0]

        if data['type'] == 'FILESYSTEM':
            for i in ('force_size', 'sparse', 'volsize', 'volblocksize'):
                if i in data:
                    verrors.add(f'{schema}.{i}', 'This field is not valid for FILESYSTEM')
        elif data['type'] == 'VOLUME':
            if mode == 'CREATE' and 'volsize' not in data:
                verrors.add(f'{schema}.volsize', 'This field is required for VOLUME')

            for i in (
                'aclmode', 'atime', 'casesensitivity', 'quota', 'refquota', 'recordsize',
            ):
                if i in data:
                    verrors.add(f'{schema}.{i}', 'This field is not valid for VOLUME')

            if 'volsize' in data and parent:

                avail_mem = int(parent['properties']['available']['rawvalue'])

                if mode == 'UPDATE':
                    avail_mem += int((await self.middleware.call(
                        'zfs.dataset.query',
                        [['id', '=', data['name']]]
                    ))[0]['properties']['used']['rawvalue'])

                if (
                    data['volsize'] > (avail_mem * 0.80) and
                    not data.get('force_size', False)
                ):
                    verrors.add(
                        f'{schema}.volsize',
                        'It is not recommended to use more than 80% of your available space for VOLUME'
                    )

                if 'volblocksize' in data:

                    if data['volblocksize'].isdigit():
                        block_size = int(data['volblocksize'])
                    else:
                        block_size = int(data['volblocksize'][:-1]) * 1024

                    if data['volsize'] % block_size:
                        verrors.add(
                            f'{schema}.volsize',
                            'Volume size should be a multiple of volume block size'
                        )

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

        dataset = await self._get_instance(id)
        path = self.__attachments_path(dataset)
        if path:
            for delegate in self.attachment_delegates:
                attachments = await delegate.query(path, True)
                if attachments:
                    await delegate.delete(attachments)

        return await self.middleware.call('zfs.dataset.delete', id, {
            'force': options['force'],
            'recursive': options['recursive'],
        })

    @item_method
    @accepts(Str('id'))
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

    @accepts(
        Str('id', required=True),
        Dict(
            'pool_dataset_permission',
            Str('user'),
            Str('group'),
            UnixPerm('mode', null=True),
            List(
                'acl',
                items=[
                    Dict(
                        'aclentry',
                        Str('tag', enum=['owner@', 'group@', 'everyone@', 'USER', 'GROUP']),
                        Int('id', null=True),
                        Str('type', enum=['ALLOW', 'DENY']),
                        Dict(
                            'perms',
                            Bool('READ_DATA'),
                            Bool('WRITE_DATA'),
                            Bool('APPEND_DATA'),
                            Bool('READ_NAMED_ATTRS'),
                            Bool('WRITE_NAMED_ATTRS'),
                            Bool('EXECUTE'),
                            Bool('DELETE_CHILD'),
                            Bool('READ_ATTRIBUTES'),
                            Bool('WRITE_ATTRIBUTES'),
                            Bool('DELETE'),
                            Bool('READ_ACL'),
                            Bool('WRITE_ACL'),
                            Bool('WRITE_OWNER'),
                            Bool('SYNCHRONIZE'),
                            Str('BASIC', enum=['FULL_CONTROL', 'MODIFY', 'READ', 'TRAVERSE']),
                        ),
                        Dict(
                            'flags',
                            Bool('FILE_INHERIT'),
                            Bool('DIRECTORY_INHERIT'),
                            Bool('NO_PROPAGATE_INHERIT'),
                            Bool('INHERIT_ONLY'),
                            Bool('INHERITED'),
                            Str('BASIC', enum=['INHERIT', 'NOINHERIT']),
                        ),
                    )
                ],
                default=[
                    {
                        "tag": "owner@",
                        "id": None,
                        "type": "ALLOW",
                        "perms": {"BASIC": "FULL_CONTROL"},
                        "flags": {"BASIC": "INHERIT"}
                    },
                    {
                        "tag": "group@",
                        "id": None,
                        "type": "ALLOW",
                        "perms": {"BASIC": "FULL_CONTROL"},
                        "flags": {"BASIC": "INHERIT"}
                    }
                ],
            ),
            Dict(
                'options',
                Bool('stripacl', default=False),
                Bool('recursive', default=False),
                Bool('traverse', default=False),
            )

        ),
    )
    @item_method
    @job(lock="dataset_permission_change")
    async def permission(self, job, id, data):
        """
        Set permissions for a dataset `id`. Permissions may be specified as
        either a posix `mode` or an nfsv4 `acl`. Setting mode will fail if the
        dataset has an existing nfsv4 acl. In this case, the option `stripacl`
        must be set to `True`.

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
                    "group": "wheel",
                    "mode": "755",
                    "options": {"recursive": true, "stripacl": true},
                }]
            }

        """
        path = (await self._get_instance(id))['mountpoint']
        user = data.get('user', None)
        group = data.get('group', None)
        uid = gid = -1
        mode = data.get('mode', None)
        options = data.get('options', {})
        acl = data.get('acl', [])
        pjob = None

        verrors = ValidationErrors()
        if user:
            try:
                uid = (await self.middleware.call('dscache.get_uncached_user', user))['pw_uid']
            except Exception as e:
                verrors.add('pool_dataset_permission.user', str(e))

        if group:
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

        if verrors:
            raise verrors

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

    @accepts(
        Str('id', required=True),
        Str('type', enum=['USER', 'GROUP']),
        Ref('query-filters'),
        Ref('query-options'),
    )
    @item_method
    async def get_user_or_group_quota(self, id, quota_type, filters, options):
        """
        Return a list of the specified `type` of  quotas on the ZFS dataset `id`.
        Support `query-filters` and `query-options`. used_bytes and used_percentage
        may not instantly update as space is used.

        Each quota entry has these fields:

        `id` - the uid or gid to which the quota applies.

        `name` - the user or group name to which the quota applies. Value is
        null if the id in the quota cannot be resolved to a user or group. This
        indicates that the user or group does not exist on the server.

        `quota` - the quota size in bytes.

        `used_bytes` - the amount of bytes the user has written to the dataset.

        `used_percentage` - the percentage of the user or group quota consumed.
        """
        dataset = (await self._get_instance(id))['name']
        quota_list = await self.middleware.call(
            'zfs.dataset.get_user_or_group_quota', dataset, quota_type.lower()
        )
        return filter_list(quota_list, filters, options)

    @accepts(
        Str('id', required=True),
        List('quotas', items=[
            Dict(
                'quota_entry',
                Str('type', enum=['USER', 'GROUP'], required=True),
                Str('id', required=True),
                Int('quota', required=True),
            )
        ], default=[{
            'type': 'USER',
            'id': '0',
            'quota': 0
        }])
    )
    @item_method
    async def set_user_or_group_quota(self, id, data):
        """
        Set a user or group quota on the specified ZFS dataset. The quota limits
        the amount of disk space consumed by files that are owned by the specified
        users or groups.

        `id` the name of the target ZFS dataset.

        `quotas` specifies a list of `quota_entry` entries to apply to dataset.

        `quota_entry` entries have these required parameters:

        `type`: specifies whether the quota applies to a user or a group.

        `id`: the uid, gid, or name to which the quota applies.

        `quota`: the quota size in bytes. Setting a value of `0` removes
        the user or group quota.
        """
        MAX_QUOTAS = 100
        dataset = (await self._get_instance(id))['name']
        verrors = ValidationErrors()
        if len(data) > MAX_QUOTAS:
            verrors.add(
                'pool.dataset.set_userquota.',
                f'The number of userspace quotas that can be set in single API call is limited to {MAX_QUOTAS}.'
            )

        quota_list = []
        for q in data:
            quota_type = q["type"].lower()
            if not q["id"].isdigit():
                try:
                    await self.middleware.call(f'{quota_type}.get_{quota_type}_obj',
                                               {f'{quota_type}name': q["id"]})
                except Exception:
                    verrors.add(
                        f'pool.dataset.set_userquota',
                        f'{q["quota_type"]} {q["id"]} is not valid.'
                    )

            quota_list.append(f'{quota_type}quota@{q["id"]}={q["quota"]}')

        verrors.check()
        quota_set = await self.middleware.call('zfs.dataset.set_user_or_group_quota',
                                               dataset, quota_list)

    @accepts(Str('pool'))
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
            raise CallError('Pool not found.', errno.ENOENT)
        pool = pool[0]
        numdisks = 4
        for vdev in pool['topology']['data']:
            if vdev['type'] == 'RAIDZ1':
                num = len(vdev['children']) - 1
            elif vdev['type'] == 'RAIDZ2':
                num = len(vdev['children']) - 2
            elif vdev['type'] == 'RAIDZ3':
                num = len(vdev['children']) - 3
            elif vdev['type'] == 'MIRROR':
                num = 1
            else:
                num = len(vdev['children'])
            if num > numdisks:
                numdisks = num
        return '%dK' % 2 ** ((numdisks * 4) - 1).bit_length()

    @item_method
    @accepts(Str('id', required=True))
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
        result = []
        dataset = await self._get_instance(oid)
        path = self.__attachments_path(dataset)
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
        result = []
        dataset = await self._get_instance(oid)
        path = self.__attachments_path(dataset)
        zvol_path = f"/dev/zvol/{dataset['name']}"
        if path:
            lsof = await run('lsof',
                             '-F', 'pcn',       # Output format parseable by `parse_lsof`
                             '-l', '-n', '-P',  # Inhibits login name, hostname and port number conversion
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, encoding='utf8')
            for pid, name in parse_lsof(lsof.stdout, [path, zvol_path]):
                service = await self.middleware.call('service.identify_process', name)
                if service:
                    result.append({
                        "pid": pid,
                        "name": name,
                        "service": service,
                    })
                else:
                    try:
                        cmdline = await self.middleware.run_in_thread(
                            lambda: psutil.Process(pid).cmdline()
                        )
                    except psutil.NoSuchProcess:
                        pass
                    else:
                        result.append({
                            "pid": pid,
                            "name": name,
                            "cmdline": join_commandline(cmdline),
                        })

        return result

    @private
    async def kill_processes(self, oid, restart_services, max_tries=5):
        manually_restart_services = []
        for process in await self.middleware.call('pool.dataset.processes', oid):
            if process.get("service") is not None:
                manually_restart_services.append(process["service"])
        if manually_restart_services and not restart_services:
            raise CallError('Some services have open files and need to be restarted', errno.EBUSY, {
                'code': 'services_restart',
                'services': manually_restart_services,
            })

        for i in range(max_tries):
            processes = await self.middleware.call('pool.dataset.processes', oid)
            if not processes:
                return

            for process in processes:
                if process.get("service") is not None:
                    self.logger.info('Restarting service %r that holds dataset %r', process['service'], oid)
                    await self.middleware.call('service.restart', process['service'])
                else:
                    self.logger.info('Killing process %r (%r) that holds dataset %r', process['pid'],
                                     process['cmdline'], oid)
                    await self.middleware.call('service.terminate_process', process['pid'])

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
        Dict(
            'pool_scrub_create',
            Int('pool', validators=[Range(min=1)], required=True),
            Int('threshold', validators=[Range(min=0)]),
            Str('description'),
            Cron(
                'schedule',
                defaults={
                    'minute': '00',
                    'hour': '00',
                    'dow': '7'
                }
            ),
            Bool('enabled', default=True),
            register=True
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

        if verrors:
            raise verrors

        data['volume'] = data.pop('pool')
        Cron.convert_schedule_to_db_format(data)

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('service.restart', 'cron')

        return await self.query(filters=[('id', '=', data['id'])], options={'get': True})

    @accepts(
        Int('id', validators=[Range(min=1)]),
        Patch('pool_scrub_create', 'pool_scrub_update', ('attr', {'update': True}))
    )
    async def do_update(self, id, data):
        """
        Update scrub task of `id`.
        """
        task_data = await self._get_instance(id)
        original_data = task_data.copy()
        task_data['original_pool_id'] = original_data['pool']
        task_data.update(data)
        verrors, task_data = await self.validate_data(task_data, 'pool_scrub_update')

        if verrors:
            raise verrors

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

        return await self._get_instance(id)

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

    @accepts(Str('name'), Int('threshold', default=35))
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
            if not await self.middleware.call('system.is_freenas'):
                if await self.middleware.call('failover.status') == 'BACKUP':
                    return

            pool = await self.middleware.call('pool.query', [['name', '=', name]], {'get': True})
            if pool['status'] == 'OFFLINE':
                if not pool['is_decrypted']:
                    raise ScrubError(f'Pool {name} is not decrypted, skipping scrub')
                else:
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

        await self.middleware.call('zfs.pool.scrub', pool['name'])
        return True


def parse_lsof(lsof, dirs):
    pids = {}

    pid = None
    command = None
    for line in lsof.split("\n"):
        if line.startswith("p"):
            pid = None
            command = None

            try:
                pid = int(line[1:])
            except ValueError:
                pass

        if line.startswith("c"):
            command = line[1:]

        if line.startswith("f"):
            pass

        if line.startswith("n"):
            path = line[1:]
            if os.path.isabs(path) and any(os.path.commonpath([path, dir]) == dir for dir in dirs):
                if pid is not None and command is not None:
                    pids[pid] = command

    return list(pids.items())


async def devd_zfs_hook(middleware, data):
    if data.get('subsystem') != 'ZFS':
        return

    if data.get('type') in (
        'ATTACH',
        'DETACH',
        'resource.fs.zfs.removed',
        'misc.fs.zfs.config_sync',
    ):
        asyncio.ensure_future(middleware.call('pool.sync_encrypted'))


def setup(middleware):
    middleware.register_hook('devd.zfs', devd_zfs_hook)
    asyncio.ensure_future(middleware.call('pool.configure_resilver_priority'))
