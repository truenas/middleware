import asyncio
import contextlib
import enum
import errno
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
from middlewared.schema import (
    accepts, Attribute, Bool, Dict, EnumMixin, Int, List, Patch, Str, UnixPerm, Any,
    Ref, returns, OROperator, NOT_PROVIDED,
)
from middlewared.plugins.pool_.utils import dataset_can_be_mounted
from middlewared.service import (
    item_method, job, private, CallError, CRUDService, ValidationErrors, periodic
)
from middlewared.utils import filter_list
from middlewared.utils.path import is_child
from middlewared.utils.size import MB
from middlewared.validators import Range

logger = logging.getLogger(__name__)


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


def _none(x):
    if x in (0, None):
        return 'none'
    return x


class PoolDatasetService(CRUDService):

    attachment_delegates = []
    dataset_store = 'storage.encrypteddataset'

    class Config:
        datastore_primary_key_type = 'string'
        namespace = 'pool.dataset'
        event_send = False
        cli_namespace = 'storage.dataset'

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
    async def delete_encrypted_datasets_from_db(self, filters):
        datasets = await self.middleware.call('datastore.query', self.dataset_store, filters)
        for ds in datasets:
            if ds['kmip_uid']:
                self.middleware.create_task(self.middleware.call('kmip.reset_zfs_key', ds['name'], ds['kmip_uid']))
            await self.middleware.call('datastore.delete', self.dataset_store, ds['id'])

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
                if err := dataset_can_be_mounted(ds['name'], os.path.join('/mnt', ds['name'])):
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
