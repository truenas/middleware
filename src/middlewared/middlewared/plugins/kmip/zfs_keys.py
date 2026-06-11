# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.alert.source.kmip import KMIPZFSDatasetsSyncFailureAlert
from middlewared.api.current import ZFSResourceQuery
from middlewared.plugins.zfs.encryption import check_key

from .connection import (
    connection_config,
    delete_kmip_secret_data,
    kmip_connection,
    register_secret_data,
    retrieve_secret_data,
    revoke_and_destroy_key,
    test_connection,
)
from .keystore import KMIPKeyStore

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.service import ServiceContext


def zfs_keys_pending_sync(context: ServiceContext, store: KMIPKeyStore) -> bool:
    config = context.call_sync2(context.s.kmip.config)
    for ds in context.middleware.call_sync('datastore.query', 'storage.encrypteddataset'):
        if config.enabled and config.manage_zfs_keys and (
            ds['encryption_key'] or ds['name'] not in store.zfs_keys
        ):
            return True
        elif (not config.enabled or not config.manage_zfs_keys) and ds['kmip_uid']:
            return True
    return False


def get_encrypted_datasets(context: ServiceContext, filters: list[Any]) -> list[dict[str, Any]]:
    rv: list[dict[str, Any]] = []
    ds_in_db: dict[str, Any] = {}
    for i in context.middleware.call_sync(
        'datastore.query',
        'storage.encrypteddataset',
        filters
    ):
        ds_in_db[i['name']] = i

    if not ds_in_db:
        return rv

    for i in context.call_sync2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(paths=list(ds_in_db), get_children=True, properties=None)
    ):
        if i['name'] in ds_in_db:
            rv.append(ds_in_db[i['name']])
    return rv


def push_zfs_keys(context: ServiceContext, store: KMIPKeyStore, tls: Any, ids: list[Any] | None = None) -> list[str]:
    failed = []
    filters = [] if ids is None else [['id', 'in', ids]]
    existing_datasets = get_encrypted_datasets(context, filters)
    with kmip_connection(context, connection_config(context)) as conn:
        for ds in existing_datasets:
            if not ds['encryption_key']:
                # We want to make sure we have the KMIP server's keys and in-memory keys in sync
                try:
                    if (
                        ds['name'] in store.zfs_keys
                        and check_key(tls, ds['name'], key=store.zfs_keys[ds['name']])
                    ):
                        continue
                    else:
                        key = retrieve_secret_data(ds['kmip_uid'], conn)
                except Exception as e:
                    context.middleware.logger.debug(f'Failed to retrieve key for {ds["name"]}: {e}')
                else:
                    store.zfs_keys[ds['name']] = key
                continue

            store.zfs_keys[ds['name']] = ds['encryption_key']
            destroy_successful = False
            if ds['kmip_uid']:
                # This needs to be revoked and destroyed
                destroy_successful = revoke_and_destroy_key(ds['kmip_uid'], conn, context.middleware.logger)
                if not destroy_successful:
                    context.middleware.logger.debug(f'Failed to destroy key from KMIP Server for {ds["name"]}')
            try:
                uid = register_secret_data(ds['name'], store.zfs_keys[ds['name']], conn)
            except Exception:
                failed.append(ds['name'])
                update_data: dict[str, Any] = {'kmip_uid': None} if destroy_successful else {}
            else:
                update_data = {'encryption_key': None, 'kmip_uid': uid}
            if update_data:
                context.middleware.call_sync('datastore.update', 'storage.encrypteddataset', ds['id'], update_data)
    store.zfs_keys = {k: v for k, v in store.zfs_keys.items() if k in existing_datasets}  # type: ignore[comparison-overlap]
    return failed


def pull_zfs_keys(context: ServiceContext, store: KMIPKeyStore, tls: Any) -> list[str]:
    existing_datasets = get_encrypted_datasets(context, [['kmip_uid', '!=', None]])
    failed = []
    connection_successful = test_connection(context)
    for ds in existing_datasets:
        try:
            if ds['encryption_key']:
                key = ds['encryption_key']
            elif (
                ds['name'] in store.zfs_keys
                and check_key(tls, ds['name'], key=store.zfs_keys[ds['name']])
            ):
                key = store.zfs_keys[ds['name']]
            elif connection_successful:
                with kmip_connection(context, connection_config(context)) as conn:
                    key = retrieve_secret_data(ds['kmip_uid'], conn)
            else:
                raise Exception('Failed to sync dataset')
        except Exception:
            failed.append(ds['name'])
        else:
            update_data = {'encryption_key': key, 'kmip_uid': None}
            context.middleware.call_sync('datastore.update', 'storage.encrypteddataset', ds['id'], update_data)
            store.zfs_keys.pop(ds['name'], None)
            if connection_successful:
                delete_kmip_secret_data(context, ds['kmip_uid'])
    store.zfs_keys = {k: v for k, v in store.zfs_keys.items() if k in existing_datasets}  # type: ignore[comparison-overlap]
    return failed


def sync_zfs_keys(
    context: ServiceContext, store: KMIPKeyStore, job: Job, tls: Any, ids: list[Any] | None = None,
) -> list[str] | None:
    if not zfs_keys_pending_sync(context, store):
        return None
    config = context.call_sync2(context.s.kmip.config)
    conn_successful = test_connection(context, None, True)
    if config.enabled and config.manage_zfs_keys:
        if conn_successful:
            failed = push_zfs_keys(context, store, tls, ids)
        else:
            return None
    else:
        failed = pull_zfs_keys(context, store, tls)
    if failed:
        context.call_sync2(
            context.s.alert.oneshot_create, KMIPZFSDatasetsSyncFailureAlert(datasets=','.join(failed))
        )
    context.middleware.call_hook_sync('kmip.zfs_keys_sync')
    return failed


async def clear_sync_pending_zfs_keys(context: ServiceContext, store: KMIPKeyStore) -> None:
    to_remove = []
    for ds in await context.middleware.call(
        'datastore.query', 'storage.encrypteddataset', [['kmip_uid', '!=', None]]
    ):
        if ds['encryption_key']:
            await context.middleware.call('datastore.update', 'storage.encrypteddataset', {'kmip_uid': None})
        else:
            to_remove.append(ds['id'])
    await context.middleware.call('datastore.delete', 'storage.encrypteddataset', [['id', 'in', to_remove]])
    store.zfs_keys = {}


def initialize_zfs_keys(context: ServiceContext, store: KMIPKeyStore, connection_success: bool) -> None:
    for ds in context.middleware.call_sync('datastore.query', 'storage.encrypteddataset',):
        if ds['encryption_key']:
            store.zfs_keys[ds['name']] = ds['encryption_key']
        elif ds['kmip_uid'] and connection_success:
            try:
                with kmip_connection(context, connection_config(context)) as conn:
                    key = retrieve_secret_data(ds['kmip_uid'], conn)
            except Exception:
                context.middleware.logger.debug(f'Failed to retrieve key for {ds["name"]}')
            else:
                store.zfs_keys[ds['name']] = key
        if ds['name'] in store.zfs_keys:
            if context.middleware.call_sync('pool.dataset.path_in_locked_datasets', ds['name']):
                context.middleware.call_sync('pool.dataset.unlock', ds['name'])


async def reset_zfs_key(context: ServiceContext, store: KMIPKeyStore, dataset: str, kmip_uid: str | None) -> None:
    store.zfs_keys.pop(dataset, None)
    if kmip_uid:
        try:
            await context.to_thread(delete_kmip_secret_data, context, kmip_uid)
        except Exception as e:
            context.middleware.logger.debug(
                f'Failed to remove encryption key from KMIP server for "{dataset}" Dataset: {e}'
            )
    await context.middleware.call_hook('kmip.zfs_keys_sync')


def update_zfs_keys(store: KMIPKeyStore, zfs_keys: dict[str, str]) -> None:
    store.zfs_keys = zfs_keys
