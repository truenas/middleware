import asyncio
import errno
import os
import shutil
import uuid

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from middlewared.schema import accepts, Bool, Dict, List, returns, Str
from middlewared.service import CallError, job, private, Service, ValidationErrors
from middlewared.validators import Range

from .utils import attachments_path, dataset_can_be_mounted, retrieve_keys_from_file, ZFSKeyFormat


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

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
        ds = await self.middleware.call('pool.dataset.get_instance_quick', id, {
            'encryption': True,
        })

        if not ds['encrypted']:
            raise CallError(f'{id} is not encrypted')
        elif ds['locked']:
            raise CallError(f'Dataset {id} is already locked')
        elif ZFSKeyFormat(ds['key_format']['value']) != ZFSKeyFormat.PASSPHRASE:
            raise CallError('Only datasets which are encrypted with passphrase can be locked')
        elif id != ds['encryption_root']:
            raise CallError(f'Please lock {ds["encryption_root"]}. Only encryption roots can be locked.')

        async def detach(delegate):
            await delegate.stop(await delegate.query(attachments_path(ds), True))

        try:
            await self.middleware.call('cache.put', 'about_to_lock_dataset', id)

            coroutines = [detach(dg) for dg in await self.middleware.call('pool.dataset.get_attachment_delegates')]
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
            keys_supplied = retrieve_keys_from_file(job)

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
                if not bool(
                    self.middleware.call_sync('pool.dataset.query_encrypted_roots_keys', [['name', '=', id]])
                ) and id not in keys_supplied:
                    verrors.add('unlock_options.datasets', f'Please specify key for {id}')

        verrors.check()

        locked_datasets = []
        datasets = self.middleware.call_sync(
            'pool.dataset.query_encrypted_datasets', id.split('/', 1)[0], {'key_loaded': False}
        )
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
        for attachment_delegate in await self.middleware.call('pool.dataset.get_attachment_delegates'):
            # FIXME: put this into `VMFSAttachmentDelegate`
            if attachment_delegate.name == 'vm':
                await self.middleware.call('pool.dataset.restart_vms_after_unlock', dataset)
                continue

            attachments = await attachment_delegate.query(attachments_path(dataset), True, {'locked': False})
            if attachments:
                await attachment_delegate.start(attachments)
