import errno
import os
import uuid

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetLockArgs, PoolDatasetLockResult, PoolDatasetUnlockArgs, PoolDatasetUnlockResult
)
from middlewared.service import CallError, job, private, Service, ValidationErrors
from middlewared.utils.filesystem.directory import directory_is_empty

from .utils import (
    dataset_mountpoint, dataset_can_be_mounted, encryption_root_children, retrieve_keys_from_file,
    ZFSKeyFormat,
)


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @api_method(PoolDatasetLockArgs, PoolDatasetLockResult, roles=['DATASET_WRITE'])
    @job(lock=lambda args: 'dataset_lock')
    async def lock(self, job, id_, options):
        """
        Locks `id` dataset. It will unmount the dataset and its children before locking.

        After the dataset has been unmounted, system will set immutable flag on the dataset's mountpoint where
        the dataset was mounted before it was locked making sure that the path cannot be modified. Once the dataset
        is unlocked, it will not be affected by this change and consumers can continue consuming it.
        """
        ds = await self.middleware.call('pool.dataset.get_instance_quick', id_, {
            'encryption': True,
        })

        if not ds['encrypted']:
            raise CallError(f'{id_} is not encrypted')
        elif ds['locked']:
            raise CallError(f'Dataset {id_} is already locked')
        elif ZFSKeyFormat(ds['key_format']['value']) != ZFSKeyFormat.PASSPHRASE:
            raise CallError('Only datasets which are encrypted with passphrase can be locked')
        elif id_ != ds['encryption_root']:
            raise CallError(f'Please lock {ds["encryption_root"]}. Only encryption roots can be locked.')

        mountpoint = dataset_mountpoint(ds)

        await self.middleware.call('pool.dataset.stop_attachment_delegates', mountpoint)

        # recursive doesn't apply to zvols
        recursive = ds['type'] != 'VOLUME'
        await self.call2(
            self.s.zfs.resource.unload_key,
            id_,
            recursive=recursive,
            force_unmount=options['force_umount'],
        )

        if ds['mountpoint']:
            await self.middleware.call('filesystem.set_zfs_attributes', {
                'path': ds['mountpoint'],
                'zfs_file_attributes': {'immutable': True}
            })

        await self.middleware.call_hook('dataset.post_lock', id_)

        return True

    @api_method(PoolDatasetUnlockArgs, PoolDatasetUnlockResult, roles=['DATASET_WRITE'])
    @job(lock=lambda args: f'dataset_unlock_{args[0]}', pipes=['input'], check_pipes=False)
    def unlock(self, job, id_, options):
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
        """
        verrors = ValidationErrors()
        dataset = self.middleware.call_sync('pool.dataset.get_instance', id_)
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
                if self.middleware.call_sync(
                    'pool.dataset.get_instance_quick', ds['name'], {'encryption': True}
                )['locked']:
                    # We are only concerned to do validation here if the dataset is locked
                    if err := dataset_can_be_mounted(ds['name'], os.path.join('/mnt', ds['name'])):
                        verrors.add(f'unlock_options.datasets.{i}.force', err)

            keys_supplied[ds['name']] = ds.get('key') or ds.get('passphrase')

        if '/' in id_ or not options['recursive']:
            if not dataset['locked']:
                verrors.add('id', f'{id_} dataset is not locked')
            elif dataset['encryption_root'] != id_:
                verrors.add('id', 'Only encryption roots can be unlocked')
            else:
                if not bool(
                    self.middleware.call_sync('pool.dataset.query_encrypted_roots_keys', [['name', '=', id_]])
                ) and id_ not in keys_supplied:
                    verrors.add('unlock_options.datasets', f'Please specify key for {id_}')

        verrors.check()

        locked_datasets = []
        datasets = self.middleware.call_sync(
            'pool.dataset.query_encrypted_datasets', id_.split('/', 1)[0], {'key_loaded': False}
        )
        self._assign_supplied_recursive_keys(options['datasets'], keys_supplied, list(datasets.keys()))

        # We're transforming dictionaries returned so that we have the following hierarchy
        #
        # datasets
        # ├── "dozer/A" (dataset dict) (encryption root)
        # |   └── "children" (list)
        # │        ├── "dozer/A/B" (dataset dict) (encryption root = dozer/A)
        # │        └── "dozer/A/B/C" (dataset dict) (encryption root = dozer/A)
        # |
        # └── "dozer/A/B/C/D" (dataset dict) (encryption root)
        #     └── "children" (list)
        #
        # e.g. at top level will be encryption roots. Only children that have same
        # encryption root as parent will be in the "children" list. The reason for this is that
        # we will iterator [parent, child1, child2, ...] when doing unlock then mount steps
        for name, ds in datasets.items():
            ds_key = keys_supplied.get(name) or ds['encryption_key']
            if ds['locked'] and id_.startswith(f'{name}/'):
                # This ensures that `id` has locked parents and they should be unlocked first
                locked_datasets.append(name)
            elif ZFSKeyFormat(ds['key_format']['value']) == ZFSKeyFormat.RAW and ds_key:
                # This is hex encoded right now - we want to change it back to raw
                try:
                    ds_key = bytes.fromhex(ds_key)
                except ValueError:
                    ds_key = None

            datasets[name] = {'key': ds_key, **ds}

            # now remove any children that are a different encryption root
            encryption_children = []
            encryption_root_children(encryption_children, ds['encryption_root'], ds)
            datasets[name]['children'] = encryption_children

        if locked_datasets:
            raise CallError(f'{id_} has locked parents {",".join(locked_datasets)} which must be unlocked first')

        failed = defaultdict(lambda: dict({'error': None, 'skipped': []}))
        unlocked = []
        names = sorted(
            filter(
                lambda n: n and f'{n}/'.startswith(f'{id_}/') and datasets[n]['locked'],
                (datasets if options['recursive'] else [id_])
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
                continue

            # Before we mount the dataset in question, we should ensure that the path where it will be mounted
            # is not already being used by some other service/share. In this case, we should simply rename the
            # directory where it will be mounted
            to_mount = [datasets[name]] + datasets[name]['children']
            for ds in to_mount:
                mount_path = os.path.join('/mnt', ds['name'])
                if os.path.exists(mount_path):

                    # possible TOCTOU on mounting dataset
                    try:
                        sfs = self.middleware.call_sync('filesystem.statfs', mount_path)
                    except Exception:
                        # don't worry about errors here, they'll be caught below
                        pass
                    else:
                        if sfs['source'] == ds['name']:
                            self.logger.debug(
                                '%s: possible race on mounting dataset. Dataset already mounted. This may '
                                'indicate multiple concurrent API calls impacting dataset locking and mounting',
                                ds['name']
                            )
                            unlocked.append(ds['name'])
                            continue

                    try:
                        self.middleware.call_sync('filesystem.set_zfs_attributes', {
                            'path': mount_path,
                            'zfs_file_attributes': {'immutable': False}
                        })
                    except OSError as e:
                        # It's ok to get `EROFS` because the dataset can have `readonly=on`
                        if e.errno != errno.EROFS:
                            raise
                    except Exception as e:
                        failed[ds['name']]['error'] = (
                            f'Dataset mount failed because immutable flag at {mount_path!r} could not be removed: {e}'
                        )
                        # Break out of this loop because any deeper paths will also fail
                        break

                    if not os.path.isdir(mount_path) or not directory_is_empty(mount_path):
                        # we already checked above that path above is not a mountpoint and we didn't have a
                        # covert mount under us of this dataset. So we should be able to simply rename here.
                        try:
                            os.rename(mount_path, f'{mount_path}-{str(uuid.uuid4())[:4]}-{datetime.now().isoformat()}')
                        except Exception as e:
                            self.logger.error('%s: failed to move unexpected directory or file from mount path',
                                              mount_path, exc_info=True)
                            failed[ds['name']]['error'] = (
                                f'Dataset mount failed because unexpected file at mount path could not be moved: {e}'
                            )
                            break

                try:
                    self.call_sync2(self.s.zfs.resource.mount, ds['name'])
                except Exception as e:
                    failed[ds['name']]['error'] = f'Failed to mount dataset: {e}'
                else:
                    unlocked.append(ds['name'])
                    try:
                        self.middleware.call_sync('filesystem.set_zfs_attributes', {
                            'path': mount_path,
                            'zfs_file_attributes': {'immutable': False}
                        })
                    except Exception:
                        pass

        for failed_ds in failed:
            failed_datasets = {}
            for ds in [failed_ds] + failed[failed_ds]['skipped']:
                mount_path = os.path.join('/mnt', ds)
                if os.path.exists(mount_path):
                    try:
                        self.middleware.call_sync('filesystem.set_zfs_attributes', {
                            'path': mount_path,
                            'zfs_file_attributes': {'immutable': True}
                        })
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

        if unlocked:
            if options['toggle_attachments']:
                job.set_progress(91, 'Handling attachments')
                # FIXME: this is incorrect design. We should be passing array of dataset names and
                # mountpoints that were *actually* unlocked rather than what was *requested* to be unlocked
                self.middleware.call_sync('pool.dataset.unlock_handle_attachments', dataset)

            job.set_progress(92, 'Updating database')

            def dataset_data(unlocked_dataset):
                return {
                    'encryption_key': keys_supplied.get(unlocked_dataset), 'name': unlocked_dataset,
                    'key_format': datasets[unlocked_dataset]['key_format']['value'],
                }

            # The following hook call and datastore insertion are for encryption records of
            # the encryption roots. This means we have checks for whether the unlocked dataset
            # is at the top level of the `datasets` dict.
            for unlocked_dataset in filter(lambda d: d in keys_supplied, unlocked):
                if unlocked_dataset not in datasets:
                    continue

                self.middleware.call_sync(
                    'pool.dataset.insert_or_update_encrypted_record', dataset_data(unlocked_dataset)
                )

            job.set_progress(94, 'Running post-unlock tasks')
            self.middleware.call_hook_sync(
                'dataset.post_unlock', datasets=[dataset_data(ds) for ds in unlocked if ds in datasets],
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
    async def unlock_handle_attachments(self, dataset):
        mountpoint = dataset_mountpoint(dataset)
        for attachment_delegate in await self.middleware.call('pool.dataset.get_attachment_delegates_for_start'):
            # FIXME: put this into `VMFSAttachmentDelegate`
            if attachment_delegate.name == 'vm':
                await self.middleware.call('pool.dataset.restart_vms_after_unlock', dataset)
                continue

            if mountpoint:
                if attachments := await attachment_delegate.query(mountpoint, True, {'locked': False}):
                    await attachment_delegate.start(attachments)
