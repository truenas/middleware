import collections
import contextlib
import errno
import json
import os
import shutil

from io import BytesIO

from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetEncryptionSummaryArgs, PoolDatasetEncryptionSummaryResult, PoolDatasetExportKeysArgs,
    PoolDatasetExportKeysResult, PoolDatasetExportKeysForReplicationArgs, PoolDatasetExportKeysForReplicationResult,
    PoolDatasetExportKeyArgs, PoolDatasetExportKeyResult
)
from middlewared.service import CallError, job, periodic, private, Service, ValidationErrors
from middlewared.service.decorators import pass_thread_local_storage
from middlewared.utils import filter_list
from middlewared.plugins.pool_.utils import get_dataset_parents
try:
    from truenas_pylibzfs import ZFSError, ZFSException
except ImportError:
    # github CI crashes without this because the
    # image on github doesn't have ZFS installed
    # so it's safe to ignore it
    ZFSError = ZFSException = None

from .utils import DATASET_DATABASE_MODEL_NAME, dataset_can_be_mounted, retrieve_keys_from_file, ZFSKeyFormat


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @api_method(PoolDatasetEncryptionSummaryArgs, PoolDatasetEncryptionSummaryResult, roles=['DATASET_READ'])
    @job(lock=lambda args: f'encryption_summary_options_{args[0]}', pipes=['input'], check_pipes=False)
    def encryption_summary(self, job, id_, options):
        """
        Retrieve summary of all encrypted roots under `id`.

        Keys/passphrase can be supplied to check if the keys are valid.

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
        datasets = self.query_encrypted_datasets(id_, {'all': True})

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
            raise CallError(f'Failed to retrieve encryption summary for {id_}: {check_job.error}')

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
    @pass_thread_local_storage
    def path_in_locked_datasets(self, tls, path):
        """
        This method checks whether the path or any
        parent components of said path are locked.
        It returns True if a locked component is
        found, otherwise False.

        Parameters:
            path (str): The filesystem path to be checked.

        Returns:
            bool: True if the path or any parent component
                of the path is locked, False otherwise.

        Raises:
            ZFSException/Exception: If an unexpected error occurs
        """
        # WARNING: _EXTREMELY_ hot code path. Do not add more
        # things here unless you fully understand the side-effects.
        if path.startswith('/dev/zvol/'):
            # 10 comes from len("/dev/zvol/")
            path = path[10:].replace('+', ' ')
        else:
            path = path.removeprefix('/mnt/')

        # Check if this path is in a dataset that's about to be locked
        # This allows services to see the dataset as locked during delegate.stop()
        # even though the key hasn't been unloaded yet
        try:
            about_to_lock = self.middleware.call_sync('cache.get', 'about_to_lock_dataset')
            if about_to_lock:
                dataset_name = path.removesuffix('/')
                if dataset_name == about_to_lock or dataset_name.startswith(f'{about_to_lock}/'):
                    return True
        except KeyError:
            pass

        for i in [path.removesuffix('/')] + get_dataset_parents(path):
            try:
                crypto = tls.lzh.open_resource(name=i).crypto()
                if crypto and not crypto.info().key_is_loaded:
                    return True
            except ZFSException as e:
                if ZFSError(e.code) in (ZFSError.EZFS_NOENT, ZFSError.EZFS_INVALIDNAME):
                    continue
                else:
                    raise
        return False

    @private
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

    @api_method(
        PoolDatasetExportKeysArgs,
        PoolDatasetExportKeysResult,
        roles=['DATASET_WRITE', 'REPLICATION_TASK_WRITE']
    )
    @job(lock='dataset_export_keys', pipes=['output'])
    def export_keys(self, job, id_):
        """
        Export keys for `id` and its children which are stored in the system. The exported file is a JSON file
        which has a dictionary containing dataset names as keys and their keys as the value.

        Please refer to websocket documentation for downloading the file.
        """
        self.middleware.call_sync('pool.dataset.get_instance_quick', id_)
        sync_job = self.middleware.call_sync('pool.dataset.sync_db_keys', id_)
        sync_job.wait_sync()

        datasets = self.query_encrypted_roots_keys([['OR', [['name', '=', id_], ['name', '^', f'{id_}/']]]])
        with BytesIO(json.dumps(datasets).encode()) as f:
            shutil.copyfileobj(f, job.pipes.output.w)

    @api_method(
        PoolDatasetExportKeysForReplicationArgs,
        PoolDatasetExportKeysForReplicationResult,
        roles=['DATASET_WRITE', 'REPLICATION_TASK_WRITE']
    )
    @job(pipes=['output'])
    def export_keys_for_replication(self, job, task_id):
        """
        Export keys for replication task `id` for source dataset(s) which are stored in the system. The exported file
        is a JSON file which has a dictionary containing dataset names as keys and their keys as the value.

        Please refer to websocket documentation for downloading the file.
        """
        task = self.middleware.call_sync('replication.get_instance', task_id)
        datasets = self.middleware.call_sync('pool.dataset.export_keys_for_replication_internal', task)
        job.pipes.output.w.write(json.dumps(datasets).encode())

    @private
    async def export_keys_for_replication_internal(
        self, replication_task_or_id, dataset_encryption_root_mapping=None, skip_syncing_db_keys=False,
    ):
        if isinstance(replication_task_or_id, int):
            task = await self.middleware.call('replication.get_instance', replication_task_or_id)
        else:
            task = replication_task_or_id
        if task['direction'] != 'PUSH':
            raise CallError('Only push replication tasks are supported.', errno.EINVAL)

        if not skip_syncing_db_keys:
            await (await self.middleware.call(
                'core.bulk', 'pool.dataset.sync_db_keys', [[source] for source in task['source_datasets']]
            )).wait()

        mapping = {}
        for source_ds in task['source_datasets']:
            source_ds_details = await self.middleware.call('pool.dataset.query', [['id', '=', source_ds]], {'extra': {
                'properties': ['encryptionroot'],
                'retrieve_children': False,
            }})
            if source_ds_details and source_ds_details[0]['encryption_root'] != source_ds:
                filters = ['name', '=', source_ds_details[0]['encryption_root']]
            else:
                if task['recursive']:
                    filters = ['OR', [['name', '=', source_ds], ['name', '^', f'{source_ds}/']]]
                else:
                    filters = ['name', '=', source_ds]
            mapping[source_ds] = await self.middleware.call('pool.dataset.query_encrypted_roots_keys', [filters])

        # We have 3 cases to deal with
        # 1. There are no encrypted datasets in source dataset, so let's just skip in that case
        # 2. There is only 1 source dataset, in this case the destination dataset will be overwritten as is, so we
        #    generate mapping accordingly. For example if source is `tank/enc` and destination is `dest/enc`, in
        #    the destination system `dest/enc` will reflect `tank/enc` so we reflect that accordingly in the mapping
        # 3. There are multiple source datasets, in this case they will become child of destination dataset

        if not any(mapping.values()):
            return {}

        result = {}
        include_encryption_root_children = not task['replicate'] and task['recursive']
        target_ds = task['target_dataset']

        source_mapping = await self.middleware.call(
            'zettarepl.get_source_target_datasets_mapping', task['source_datasets'], target_ds
        )
        if include_encryption_root_children:
            dataset_mapping = dataset_encryption_root_mapping or await self.dataset_encryption_root_mapping()
        else:
            dataset_mapping = {}

        for source_ds in task['source_datasets']:
            for ds_name, key in mapping[source_ds].items():
                for dataset in (dataset_mapping[ds_name] if include_encryption_root_children else [{'id': ds_name}]):
                    result[dataset['id'].replace(
                        source_ds if len(source_ds) <= len(dataset['id']) else dataset['id'],
                        source_mapping[source_ds], 1
                    )] = key

        return result

    @private
    async def dataset_encryption_root_mapping(self):
        dataset_encryption_root_mapping = collections.defaultdict(list)
        for dataset in await self.middleware.call(
            'pool.dataset.query', [], {'extra': {'properties': ['encryptionroot']}}
        ):
            dataset_encryption_root_mapping[dataset['encryption_root']].append(dataset)

        return dataset_encryption_root_mapping

    @api_method(PoolDatasetExportKeyArgs, PoolDatasetExportKeyResult, roles=['DATASET_WRITE'])
    @job(lock='dataset_export_keys', pipes=['output'], check_pipes=False)
    def export_key(self, job, id_, download):
        """
        Export own encryption key for dataset `id`. If `download` is `true`, key will be downloaded in a json file
        where the same file can be used to unlock the dataset, otherwise it will be returned as string.

        Please refer to websocket documentation for downloading the file.
        """
        if download:
            job.check_pipe('output')

        self.middleware.call_sync('pool.dataset.get_instance_quick', id_)

        keys = self.query_encrypted_roots_keys([['name', '=', id_]])
        if id_ not in keys:
            raise CallError('Specified dataset does not have it\'s own encryption key.', errno.EINVAL)

        key = keys[id_]

        if download:
            job.pipes.output.w.write(json.dumps({id_: key}).encode())
        else:
            return key
