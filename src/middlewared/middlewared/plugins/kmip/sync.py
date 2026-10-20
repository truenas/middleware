# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .connection import test_connection
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
    initialize_zfs_keys,
    update_zfs_keys,
    zfs_keys_pending_sync,
)

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.service import ServiceContext


def kmip_sync_pending(context: ServiceContext, store: KMIPKeyStore) -> bool:
    return zfs_keys_pending_sync(context, store) or sed_keys_pending_sync(context, store)


async def sync_keys(context: ServiceContext, store: KMIPKeyStore) -> None:
    if not await context.to_thread(kmip_sync_pending, context, store) or \
            not await context.middleware.call('failover.is_single_master_node'):
        return
    await context.call2(context.s.kmip.sync_zfs_keys)
    await context.call2(context.s.kmip.sync_sed_keys)


async def clear_sync_pending_keys(context: ServiceContext, store: KMIPKeyStore) -> None:
    config = await context.call2(context.s.kmip.config)
    clear = not config.enabled
    if clear or not config.manage_zfs_keys:
        await clear_sync_pending_zfs_keys(context, store)
    if clear or not config.manage_sed_disks:
        await clear_sync_pending_sed_keys(context, store)


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
