import asyncio
import contextlib
import copy
import enum
import errno
import itertools
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import os
import re
import secrets
import shutil
import uuid

from collections import defaultdict
from io import BytesIO

from middlewared.alert.base import AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass
from middlewared.plugins.pool_.utils import ZPOOL_CACHE_FILE, ZFS_CHECKSUM_CHOICES, ZFS_ENCRYPTION_ALGORITHM_CHOICES
from middlewared.plugins.zfs import ZFSSetPropertyError
from middlewared.plugins.zfs_.validation_utils import validate_dataset_name
from middlewared.schema import (
    accepts, Attribute, Bool, Dict, EnumMixin, Int, List, Patch, Str, UnixPerm, Any,
    Ref, returns, OROperator, NOT_PROVIDED,
)
from middlewared.service import (
    filterable, item_method, job, pass_app, private, CallError, CRUDService, ValidationErrors, periodic
)
from middlewared.service_exception import ValidationError
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list
from middlewared.utils.path import is_child
from middlewared.utils.size import MB
from middlewared.validators import Exact, Match, Or, Range

logger = logging.getLogger(__name__)

RE_HISTORY_ZPOOL_CREATE = re.compile(r'^([0-9\.\:\-]{19})\s+zpool create', re.MULTILINE)

ZFS_COMPRESSION_ALGORITHM_CHOICES = [
    'OFF', 'LZ4', 'GZIP', 'GZIP-1', 'GZIP-9', 'ZSTD', 'ZSTD-FAST', 'ZLE', 'LZJB',
] + [f'ZSTD-{i}' for i in range(1, 20)] + [
    f'ZSTD-FAST-{i}' for i in itertools.chain(range(1, 11), range(20, 110, 10), range(500, 1500, 500))
]
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
                self.middleware.create_task(self.middleware.call('kmip.reset_zfs_key', ds['name'], ds['kmip_uid']))
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
    def path_in_locked_datasets(self, path, locked_datasets=None):
        if locked_datasets is None:
            locked_datasets = self.middleware.call_sync('zfs.dataset.locked_datasets')
        return any(is_child(path, d['mountpoint']) for d in locked_datasets if d['mountpoint'])

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
        Inheritable(Str('casesensitivity', enum=['SENSITIVE', 'INSENSITIVE']), has_default=False),
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

        if await self.middleware.call('pool.dataset.is_internal_dataset', data['name']):
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
        Str('quota_type', enum=['USER', 'GROUP', 'DATASET', 'PROJECT']),
        Ref('query-filters'),
        Ref('query-options'),
    )
    @item_method
    async def get_quota(self, ds, quota_type, filters, options):
        """
        Return a list of the specified `quota_type` of quotas on the ZFS dataset `ds`.
        Support `query-filters` and `query-options`. used_bytes may not instantly
        update as space is used.

        When quota_type is not DATASET, each quota entry has these fields:

        `id` - the uid or gid to which the quota applies.

        `name` - the user or group name to which the quota applies. Value is
        null if the id in the quota cannot be resolved to a user or group. This
        indicates that the user or group does not exist on the server.

        `quota` - the quota size in bytes.  Absent if no quota is set.

        `used_bytes` - the amount of bytes the user has written to the dataset.
        A value of zero means unlimited.

        `obj_quota` - the number of objects that may be owned by `id`.
        A value of zero means unlimited.  Absent if no objquota is set.

        `obj_used` - the number of objects currently owned by `id`.

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
        verrors = ValidationErrors()
        if len(data) > MAX_QUOTAS:
            verrors.add(
                'quotas',
                f'The number of user or group quotas that can be set in single API call is limited to {MAX_QUOTAS}.'
            )

        quotas = {}

        for i, q in enumerate(data):
            quota_type = q['quota_type'].lower()
            if q['quota_type'] == 'DATASET':
                if q['id'] not in ['QUOTA', 'REFQUOTA']:
                    verrors.add(
                        f'quotas.{i}.id',
                        'id for quota_type DATASET must be either "QUOTA" or "REFQUOTA"'
                    )
                    continue

                xid = q['id'].lower()
                if xid in quotas:
                    verrors.add(
                        f'quotas.{i}.id',
                        f'Setting multiple values for {xid} for quota_type "DATASET" is not permitted'
                    )
                    continue

            elif q['quota_type'] not in ['PROJECT', 'PROJECTOBJ']:
                if not q['quota_value']:
                    q['quota_value'] = 'none'

                xid = None

                id_type = 'user' if quota_type.startswith('user') else 'group'
                if not q['id'].isdigit():
                    try:
                        xid_obj = await self.middleware.call(f'{id_type}.get_{id_type}_obj',
                                                             {f'{id_type}name': q['id']})
                        xid = xid_obj['pw_uid'] if id_type == 'user' else xid_obj['gr_gid']
                    except Exception:
                        self.logger.debug("Failed to convert %s [%s] to id.", id_type, q['id'], exc_info=True)
                        verrors.add(
                            f'quotas.{i}.id',
                            f'{quota_type} {q["id"]} is not valid.'
                        )
                else:
                    xid = int(q['id'])

                if xid == 0:
                    verrors.add(
                        f'quotas.{i}.id',
                        f'Setting {quota_type} quota on {id_type[0]}id [{xid}] is not permitted.'
                    )
            else:
                if not q['id'].isdigit():
                    verrors.add(
                        f'quotas.{i}.id',
                        f'{quota_type} {q["id"]} must be a numeric project id.'
                    )
                xid = int(q['id'])

            quotas[xid] = q

        verrors.check()
        if quotas:
            await self.middleware.call('zfs.dataset.set_quota', ds, quotas)

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
