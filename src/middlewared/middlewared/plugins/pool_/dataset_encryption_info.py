import contextlib
import errno
import json
import os
import shutil

from io import BytesIO

from middlewared.schema import accepts, Bool, Dict, List, Ref, returns, Str
from middlewared.service import CallError, job, periodic, private, Service, ValidationErrors
from middlewared.utils import filter_list
from middlewared.utils.path import is_child_realpath
from middlewared.validators import Range

from .utils import DATASET_DATABASE_MODEL_NAME, dataset_can_be_mounted, retrieve_keys_from_file, ZFSKeyFormat


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

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
            keys_supplied = {k: {'key': v, 'force': False} for k, v in retrieve_keys_from_file(job).items()}

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
                err = dataset_can_be_mounted(ds['name'], os.path.join('/mnt', ds['name']))
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
            d['name']: d for d in self.middleware.call_sync(
                'pool.dataset.query', filters, {'extra': {'properties': ['encryptionroot']}}
            ) if d['name'] == d['encryption_root']
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
    def path_in_locked_datasets(self, path, locked_datasets=None):
        if locked_datasets is None:
            locked_datasets = self.middleware.call_sync('zfs.dataset.locked_datasets')
        return any(is_child_realpath(path, d['mountpoint']) for d in locked_datasets if d['mountpoint'])

    @private
    @accepts(Ref('query-filters'))
    def query_encrypted_roots_keys(self, filters):
        # We query database first - if we are able to find an encryption key, we assume it's the correct one.
        # If we are unable to find the key in database, we see if we have it in memory with the KMIP server, if not,
        # there are 2 ways this can go, we don't retrieve the key or the user can sync KMIP keys and we will have it
        # with the KMIP service again through which we can retrieve them
        datasets = filter_list(self.middleware.call_sync('datastore.query', DATASET_DATABASE_MODEL_NAME), filters)
        zfs_keys = self.middleware.call_sync('kmip.retrieve_zfs_keys')
        keys = {}
        for ds in datasets:
            if ds['encryption_key']:
                keys[ds['name']] = ds['encryption_key']
            elif ds['name'] in zfs_keys:
                keys[ds['name']] = zfs_keys[ds['name']]
        return keys

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
                lambda d: (
                    d['name'] == d['encryption_root'] and d['encrypted'] and f'{d["name"]}/'.startswith(
                        f'{name}/'
                    ) and check_key(d)
                ),
                self.middleware.call_sync('pool.dataset.query')
            )
        ))

    @accepts(Str('id'))
    @returns()
    @job(lock='dataset_export_keys', pipes=['output'])
    def export_keys(self, job, id):
        """
        Export keys for `id` and its children which are stored in the system. The exported file is a JSON file
        which has a dictionary containing dataset names as keys and their keys as the value.

        Please refer to websocket documentation for downloading the file.
        """
        self.middleware.call_sync('pool.dataset.get_instance_quick', id)
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

        self.middleware.call_sync('pool.dataset.get_instance_quick', id)

        keys = self.query_encrypted_roots_keys([['name', '=', id]])
        if id not in keys:
            raise CallError('Specified dataset does not have it\'s own encryption key.', errno.EINVAL)

        key = keys[id]

        if download:
            job.pipes.output.w.write(json.dumps({id: key}).encode())
        else:
            return key
