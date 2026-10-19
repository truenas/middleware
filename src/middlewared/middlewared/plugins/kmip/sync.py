# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .connection import push_direction, test_connection
from .keystore import KMIPKeyStore
from .sed_keys import (
    clear_sync_pending_sed_keys,
    initialize_sed_keys,
    sed_keys,
    sed_keys_pending_sync,
    update_sed_keys,
)
from .zfs_keys import (
    clear_sync_pending_zfs_keys,
    get_encrypted_datasets,
    initialize_zfs_keys,
    update_zfs_keys,
    zfs_keys_pending_sync,
)

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.service import ServiceContext


def kmip_sync_pending(context: ServiceContext, store: KMIPKeyStore) -> bool:
    return (
        zfs_keys_pending_sync(context, store, push_direction(context, 'manage_zfs_keys'))
        or sed_keys_pending_sync(context, store, push_direction(context, 'manage_sed_disks'))
    )


async def sync_keys(context: ServiceContext, store: KMIPKeyStore) -> None:
    if not await context.to_thread(kmip_sync_pending, context, store) or \
            not await context.middleware.call('failover.is_single_master_node'):
        return
    for method in ('kmip.sync_zfs_keys', 'kmip.sync_sed_keys'):
        await (await context.middleware.call(method, job_silent=True)).wait(raise_error=True)


async def escrowed_count(context: ServiceContext) -> int:
    datasets = await context.to_thread(get_encrypted_datasets, context, [['kmip_uid', '!=', None]])
    disks: int = await context.middleware.call(
        'datastore.query', 'storage.disk', [['kmip_uid', '!=', None], ['expiretime', '=', None]],
        {'prefix': 'disk_', 'count': True},
    )
    adv_config = await context.middleware.call('datastore.config', 'system.advanced', {'prefix': 'adv_'})
    return len(datasets) + disks + bool(adv_config['kmip_uid'])


async def clear_sync_pending_keys(context: ServiceContext, store: KMIPKeyStore) -> None:
    config = await context.call2(context.s.kmip.config)
    clear = not config.enabled
    if clear or not config.manage_zfs_keys:
        await clear_sync_pending_zfs_keys(context, store)
    if clear or not config.manage_sed_disks:
        await clear_sync_pending_sed_keys(context, store)


async def clear_pulled_kmip_uids(context: ServiceContext) -> None:
    for ds in await context.middleware.call(
        'datastore.query', 'storage.encrypteddataset', [['kmip_uid', '!=', None]]
    ):
        if ds['encryption_key']:
            await context.middleware.call('datastore.update', 'storage.encrypteddataset', ds['id'], {'kmip_uid': None})
    for disk in await context.middleware.call(
        'datastore.query', 'storage.disk', [['kmip_uid', '!=', None]], {'prefix': 'disk_'}
    ):
        if disk['passwd']:
            await context.middleware.call(
                'datastore.update', 'storage.disk', disk['identifier'], {'disk_kmip_uid': None}
            )
    adv_config = await context.middleware.call('datastore.config', 'system.advanced', {'prefix': 'adv_'})
    if adv_config['kmip_uid'] and adv_config['sed_passwd']:
        await context.middleware.call('datastore.update', 'system.advanced', adv_config['id'], {'adv_kmip_uid': None})


async def initialize_keys(context: ServiceContext, store: KMIPKeyStore, job: Job) -> None:
    kmip_config = await context.call2(context.s.kmip.config)
    if kmip_config.enabled and await context.middleware.call('failover.is_single_master_node'):
        connection_success = await context.to_thread(
            test_connection, context, None, kmip_config.manage_zfs_keys or kmip_config.manage_sed_disks
        )
        if kmip_config.manage_zfs_keys:
            await context.to_thread(initialize_zfs_keys, context, store, connection_success)
        if kmip_config.manage_sed_disks:
            await context.to_thread(initialize_sed_keys, context, store, connection_success)


def kmip_memory_keys(store: KMIPKeyStore) -> dict[str, Any]:
    return {
        'zfs': store.zfs_keys,
        'sed': sed_keys(store),
    }


def update_memory_keys(store: KMIPKeyStore, data: dict[str, Any]) -> None:
    if 'zfs' in data:
        update_zfs_keys(store, data['zfs'])
    if 'sed' in data:
        update_sed_keys(store, data['sed'])
