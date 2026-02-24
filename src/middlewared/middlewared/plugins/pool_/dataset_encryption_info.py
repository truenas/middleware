from __future__ import annotations

import collections
import contextlib
import errno
from io import BytesIO
import json
import os
import shutil
from typing import TYPE_CHECKING

from truenas_pylibzfs import ZFSError, ZFSException

from middlewared.service import CallError, ValidationErrors
from middlewared.utils.filter_list import filter_list
from middlewared.plugins.pool_.utils import get_dataset_parents

if TYPE_CHECKING:
    from middlewared.api.current import (
        PoolDatasetEncryptionSummary,
        PoolDatasetEncryptionSummaryOptions,
    )
    from middlewared.job import Job
    from middlewared.service import ServiceContext
    import threading

from .utils import DATASET_DATABASE_MODEL_NAME, dataset_can_be_mounted, retrieve_keys_from_file, ZFSKeyFormat


def encryption_summary_impl(ctx: ServiceContext, job: Job, id_: str, options: PoolDatasetEncryptionSummaryOptions) -> list[PoolDatasetEncryptionSummary]:
    keys_supplied = {}
    verrors = ValidationErrors()
    if options.key_file:
        keys_supplied = {k: {'key': v, 'force': False} for k, v in retrieve_keys_from_file(job).items()}

    for i, ds in enumerate(options.datasets):
        ds_key = getattr(ds, 'key', None)
        ds_passphrase = getattr(ds, 'passphrase', None)
        if ds_key and ds_passphrase:
            verrors.add(
                f'unlock_options.datasets.{i}.dataset.key',
                f'Must not be specified when passphrase for {ds.name} is supplied'
            )
        keys_supplied[ds.name] = {
            'key': ds_key or ds_passphrase,
            'force': ds.force,
        }

    verrors.check()
    datasets = query_encrypted_datasets(ctx, id_, {'all': True})

    to_check = []
    for name, ds in datasets.items():
        ds_key = keys_supplied.get(name, {}).get('key') or ds['encryption_key']
        if ZFSKeyFormat(ds['key_format']['value']) == ZFSKeyFormat.RAW and ds_key:
            with contextlib.suppress(ValueError):
                ds_key = bytes.fromhex(ds_key)
        to_check.append((name, {'key': ds_key}))

    check_job = ctx.middleware.call_sync('zfs.dataset.bulk_process', 'check_key', to_check)
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

        if ds['locked'] and not options.force and not keys_supplied.get(ds['name'], {}).get('force'):
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


def sync_db_keys_impl(ctx: ServiceContext, job: Job, name: str | None = None) -> None:
    if not ctx.middleware.call_sync('failover.is_single_master_node'):
        # We don't want to do this for passive controller
        return
    filters = [['OR', [['name', '=', name], ['name', '^', f'{name}/']]]] if name else []

    # It is possible we have a pool configured but for some mistake/reason the pool did not import like
    # during repair disks were not plugged in and system was booted, in such cases we would like to not
    # remove the encryption keys from the database.
    for root_ds in {pool['name'] for pool in ctx.middleware.call_sync('pool.query')} - {
        ds['id'] for ds in ctx.middleware.call_sync(
            'pool.dataset.query', [], {'extra': {'retrieve_children': False, 'properties': []}}
        )
    }:
        filters.extend([['name', '!=', root_ds], ['name', '!^', f'{root_ds}/']])

    db_datasets = query_encrypted_roots_keys(ctx, filters)
    encrypted_roots = {
        d['name']: d for d in ctx.middleware.call_sync(
            'pool.dataset.query', filters, {'extra': {'properties': ['encryptionroot']}}
        ) if d['name'] == d['encryption_root']
    }
    to_remove = []
    check_key_job = ctx.middleware.call_sync('zfs.dataset.bulk_process', 'check_key', [
        (name, {'key': db_datasets[name]}) for name in db_datasets
    ])
    check_key_job.wait_sync()
    if check_key_job.error:
        ctx.logger.error(f'Failed to sync database keys: {check_key_job.error}')
        return

    for dataset, status in zip(db_datasets, check_key_job.result):
        if not status['result']:
            to_remove.append(dataset)
        elif status['error']:
            if dataset not in encrypted_roots:
                to_remove.append(dataset)
            else:
                ctx.logger.error(f'Failed to check encryption status for {dataset}: {status["error"]}')

    # TODO: Convert to call_sync2 once delete_encrypted_datasets_from_db is refactored
    ctx.middleware.call_sync('pool.dataset.delete_encrypted_datasets_from_db', [['name', 'in', to_remove]])


def path_in_locked_datasets(tls: threading.local, path: str) -> bool:
    """
    Check whether the path or any parent components of said path are locked.

    WARNING: EXTREMELY hot code path. Do not add more things here unless
    you fully understand the side-effects.

    Parameters:
        path (str): The filesystem path to be checked.

    Returns:
        bool: True if the path or any parent component of the path is locked, False otherwise.

    Raises:
        ZFSException/Exception: If an unexpected error occurs
    """
    if path.startswith('/dev/zvol/'):
        # 10 comes from len("/dev/zvol/")
        path = path[10:].replace('+', ' ')
    else:
        path = path.removeprefix('/mnt/')

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


def query_encrypted_roots_keys(ctx: ServiceContext, filters: list) -> dict[str, str]:
    """Query encryption keys from database and KMIP for encrypted datasets."""
    # We query database first - if we are able to find an encryption key, we assume it's the correct one.
    # If we are unable to find the key in database, we see if we have it in memory with the KMIP server
    datasets = filter_list(ctx.middleware.call_sync('datastore.query', DATASET_DATABASE_MODEL_NAME), filters)
    zfs_keys = ctx.middleware.call_sync('kmip.retrieve_zfs_keys')
    keys = {}
    for ds in datasets:
        if ds['encryption_key']:
            keys[ds['name']] = ds['encryption_key']
        elif ds['name'] in zfs_keys:
            keys[ds['name']] = zfs_keys[ds['name']]
    return keys


def query_encrypted_datasets(ctx: ServiceContext, name: str, options: dict | None = None) -> dict[str, dict]:
    """Common function to retrieve encrypted datasets."""
    options = options or {}
    key_loaded = options.get('key_loaded', True)
    db_results = query_encrypted_roots_keys(ctx, [['OR', [['name', '=', name], ['name', '^', f'{name}/']]]])

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
            ctx.middleware.call_sync('pool.dataset.query')
        )
    ))


def export_keys_impl(ctx: ServiceContext, job: Job, id_: str) -> None:
    ctx.call_sync2(ctx.s.pool.dataset.get_instance_quick, id_)
    sync_job = ctx.middleware.call_sync('pool.dataset.sync_db_keys', id_)
    sync_job.wait_sync()

    datasets = query_encrypted_roots_keys(ctx, [['OR', [['name', '=', id_], ['name', '^', f'{id_}/']]]])
    with BytesIO(json.dumps(datasets).encode()) as f:
        shutil.copyfileobj(f, job.pipes.output.w)


def export_keys_for_replication_impl(ctx: ServiceContext, job: Job, task_id: int) -> None:
    task = ctx.middleware.call_sync('replication.get_instance', task_id)
    datasets = ctx.middleware.call_sync('pool.dataset.export_keys_for_replication_internal', task)
    job.pipes.output.w.write(json.dumps(datasets).encode())


async def export_keys_for_replication_internal(
    ctx: ServiceContext,
    replication_task_or_id: int | dict,
    dataset_encryption_root_mapping: dict | None = None,
    skip_syncing_db_keys: bool = False,
) -> dict[str, str]:
    if isinstance(replication_task_or_id, int):
        task = await ctx.middleware.call('replication.get_instance', replication_task_or_id)
    else:
        task = replication_task_or_id
    if task['direction'] != 'PUSH':
        raise CallError('Only push replication tasks are supported.', errno.EINVAL)

    if not skip_syncing_db_keys:
        await (await ctx.middleware.call(
            'core.bulk', 'pool.dataset.sync_db_keys', [[source] for source in task['source_datasets']]
        )).wait()

    mapping = {}
    for source_ds in task['source_datasets']:
        source_ds_details = await ctx.middleware.call('pool.dataset.query', [['id', '=', source_ds]], {'extra': {
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
        # TODO: Convert to call2 once query_encrypted_roots_keys is available via call2
        mapping[source_ds] = await ctx.middleware.call('pool.dataset.query_encrypted_roots_keys', [filters])

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

    source_mapping = await ctx.middleware.call(
        'zettarepl.get_source_target_datasets_mapping', task['source_datasets'], target_ds
    )
    if include_encryption_root_children:
        dataset_mapping = dataset_encryption_root_mapping or await dataset_encryption_root_mapping_impl(ctx)
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


async def dataset_encryption_root_mapping_impl(ctx: ServiceContext) -> dict[str, list[dict]]:
    """Build mapping of encryption roots to their child datasets."""
    dataset_encryption_root_mapping = collections.defaultdict(list)
    for dataset in await ctx.middleware.call(
        'pool.dataset.query', [], {'extra': {'properties': ['encryptionroot']}}
    ):
        dataset_encryption_root_mapping[dataset['encryption_root']].append(dataset)

    return dataset_encryption_root_mapping


def export_key_impl(ctx: ServiceContext, job: Job, id_: str, download: bool) -> str | None:
    if download:
        job.check_pipe('output')

    ctx.call_sync2(ctx.s.pool.dataset.get_instance_quick, id_)

    keys = query_encrypted_roots_keys(ctx, [['name', '=', id_]])
    if id_ not in keys:
        raise CallError('Specified dataset does not have it\'s own encryption key.', errno.EINVAL)

    key = keys[id_]

    if download:
        job.pipes.output.w.write(json.dumps({id_: key}).encode())
        return None
    else:
        return key
