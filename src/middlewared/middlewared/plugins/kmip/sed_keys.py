# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.alert.source.kmip import KMIPSEDDisksSyncFailureAlert, KMIPSEDGlobalPasswordSyncFailureAlert

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


"""
SED keys are stored in 2 places:
1) system.advanced table
2) storage.disk table

There are 3 possible cases which we need to handle for storage.disk
1) A disk row can have SED key
2) A disk row can have a blank SED key
3) A disk row can be removed

There are 2 possible cases which we need to handle for system.advanced
1) system.advanced.config can have global SED password
2) system.advanced.config cannot have global SED password
"""


def sed_keys_pending_sync(context: ServiceContext, store: KMIPKeyStore) -> bool:
    adv_config = context.middleware.call_sync('datastore.config', 'system.advanced', {'prefix': 'adv_'})
    disks = context.middleware.call_sync('datastore.query', 'storage.disk', [], {'prefix': 'disk_'})
    config = context.call_sync2(context.s.kmip.config)
    check_db_key = config.enabled and config.manage_sed_disks
    for disk in disks:
        if check_db_key and (disk['passwd'] or (disk['kmip_uid'] and disk['identifier'] not in store.disks_keys)):
            return True
        elif not check_db_key and disk['kmip_uid']:
            return True
    if check_db_key and (adv_config['sed_passwd'] or (not store.global_sed_key and adv_config['kmip_uid'])):
        return True
    elif not check_db_key and adv_config['kmip_uid']:
        return True
    return False


def push_sed_keys(context: ServiceContext, store: KMIPKeyStore, ids: list[Any] | None = None) -> list[str]:
    adv_config = context.middleware.call_sync('datastore.config', 'system.advanced', {'prefix': 'adv_'})
    failed = []
    with kmip_connection(context, connection_config(context)) as conn:
        for disk in context.middleware.call_sync(
            'datastore.query', 'storage.disk', [['identifier', 'in', ids]] if ids else [], {'prefix': 'disk_'}
        ):
            if not disk['passwd'] and disk['kmip_uid']:
                try:
                    key = retrieve_secret_data(disk['kmip_uid'], conn)
                except Exception as e:
                    context.middleware.logger.debug(f'Failed to retrieve key for {disk["identifier"]}: {e}')
                else:
                    store.disks_keys[disk['identifier']] = key
                continue
            elif not disk['passwd']:
                continue

            store.disks_keys[disk['identifier']] = disk['passwd']
            destroy_successful = False
            if disk['kmip_uid']:
                # This needs to be revoked and destroyed
                destroy_successful = revoke_and_destroy_key(
                    disk['kmip_uid'], conn, context.middleware.logger, disk['identifier']
                )
            try:
                uid = register_secret_data(disk['identifier'], store.disks_keys[disk['identifier']], conn)
            except Exception:
                failed.append(disk['identifier'])
                update_data: dict[str, Any] = {'kmip_uid': None} if destroy_successful else {}
            else:
                update_data = {'passwd': '', 'kmip_uid': uid}
            if update_data:
                context.middleware.call_sync(
                    'datastore.update', 'storage.disk', disk['identifier'], update_data, {'prefix': 'disk_'}
                )
        if not adv_config['sed_passwd'] and adv_config['kmip_uid']:
            try:
                key = retrieve_secret_data(adv_config['kmip_uid'], conn)
            except Exception:
                failed.append('Global SED Key')
            else:
                store.global_sed_key = key
        elif adv_config['sed_passwd']:
            if adv_config['kmip_uid']:
                revoke_and_destroy_key(
                    adv_config['kmip_uid'], conn, context.middleware.logger, 'SED Global Password'
                )
                context.middleware.call_sync(
                    'datastore.update', 'system.advanced', adv_config['id'], {'adv_kmip_uid': None}
                )
            store.global_sed_key = adv_config['sed_passwd']
            try:
                uid = register_secret_data('global_sed_key', store.global_sed_key, conn)
            except Exception:
                failed.append('Global SED Key')
            else:
                context.middleware.call_sync(
                    'datastore.update', 'system.advanced',
                    adv_config['id'], {'adv_sed_passwd': '', 'adv_kmip_uid': uid}
                )
    return failed


def pull_sed_keys(context: ServiceContext, store: KMIPKeyStore) -> list[str]:
    failed = []
    connection_successful = test_connection(context)
    for disk in context.middleware.call_sync(
        'datastore.query', 'storage.disk', [['kmip_uid', '!=', None]], {'prefix': 'disk_'}
    ):
        try:
            if disk['passwd']:
                key = disk['passwd']
            elif store.disks_keys.get(disk['identifier']):
                key = store.disks_keys[disk['identifier']]
            elif connection_successful:
                with kmip_connection(context, connection_config(context)) as conn:
                    key = retrieve_secret_data(disk['kmip_uid'], conn)
            else:
                raise Exception('Failed to sync disk')
        except Exception:
            failed.append(disk['identifier'])
        else:
            update_data = {'passwd': key, 'kmip_uid': None}
            context.middleware.call_sync(
                'datastore.update', 'storage.disk', disk['identifier'], update_data, {'prefix': 'disk_'}
            )
            store.disks_keys.pop(disk['identifier'], None)
            if connection_successful:
                delete_kmip_secret_data(context, disk['kmip_uid'])
    adv_config = context.middleware.call_sync('datastore.config', 'system.advanced', {'prefix': 'adv_'})
    if adv_config['kmip_uid']:
        key = None
        if adv_config['sed_passwd']:
            key = adv_config['sed_passwd']
        elif store.global_sed_key:
            key = store.global_sed_key
        elif connection_successful:
            try:
                with kmip_connection(context, connection_config(context)) as conn:
                    key = retrieve_secret_data(adv_config['kmip_uid'], conn)
            except Exception:
                failed.append('Global SED Key')
        if key:
            context.middleware.call_sync(
                'datastore.update', 'system.advanced',
                adv_config['id'], {
                    'adv_sed_passwd': key, 'adv_kmip_uid': None
                }
            )
            store.global_sed_key = ''
            if connection_successful:
                delete_kmip_secret_data(context, adv_config['kmip_uid'])
    return failed


def sync_sed_keys(
    context: ServiceContext, store: KMIPKeyStore, job: Job, ids: list[Any] | None = None,
) -> list[str] | None:
    if not sed_keys_pending_sync(context, store):
        return None
    config = context.call_sync2(context.s.kmip.config)
    conn_successful = test_connection(context, None, True)
    if config.enabled and config.manage_sed_disks:
        if conn_successful:
            failed = push_sed_keys(context, store, ids)
        else:
            return None
    else:
        failed = pull_sed_keys(context, store)
    ret_failed = failed.copy()
    try:
        failed.remove('Global SED Key')
    except ValueError:
        pass
    else:
        context.call_sync2(context.s.alert.oneshot_create, KMIPSEDGlobalPasswordSyncFailureAlert())
    finally:
        if failed:
            context.call_sync2(
                context.s.alert.oneshot_create, KMIPSEDDisksSyncFailureAlert(disks=','.join(failed))
            )
    context.middleware.call_hook_sync('kmip.sed_keys_sync')
    return ret_failed


async def clear_sync_pending_sed_keys(context: ServiceContext, store: KMIPKeyStore) -> None:
    for disk in await context.middleware.call(
        'datastore.query', 'storage.disk', [['kmip_uid', '!=', None]], {'prefix': 'disk_'}
    ):
        await context.middleware.call(
            'datastore.update', 'storage.disk', disk['identifier'], {'disk_kmip_uid': None}
        )
    adv_config = await context.middleware.call('datastore.config', 'system.advanced', {'prefix': 'adv_'})
    if adv_config['kmip_uid']:
        await context.middleware.call(
            'datastore.update', 'system.advanced', adv_config['id'], {'adv_kmip_uid': None}
        )
    store.global_sed_key = ''
    store.disks_keys = {}


def initialize_sed_keys(context: ServiceContext, store: KMIPKeyStore, connection_success: bool) -> None:
    for disk in context.middleware.call_sync(
        'datastore.query', 'storage.disk', [], {'prefix': 'disk_'}
    ):
        if disk['passwd']:
            store.disks_keys[disk['identifier']] = disk['passwd']
        elif disk['kmip_uid'] and connection_success:
            try:
                with kmip_connection(context, connection_config(context)) as conn:
                    key = retrieve_secret_data(disk['kmip_uid'], conn)
            except Exception:
                context.middleware.logger.debug(f'Failed to retrieve SED disk key for {disk["identifier"]}')
            else:
                store.disks_keys[disk['identifier']] = key
    adv_config = context.middleware.call_sync('datastore.config', 'system.advanced', {'prefix': 'adv_'})
    if adv_config['sed_passwd']:
        store.global_sed_key = adv_config['sed_passwd']
    elif connection_success and adv_config['kmip_uid']:
        try:
            with kmip_connection(context, connection_config(context)) as conn:
                key = retrieve_secret_data(adv_config['kmip_uid'], conn)
        except Exception:
            context.middleware.logger.debug('Failed to retrieve global SED key')
        else:
            store.global_sed_key = key


def update_sed_keys(store: KMIPKeyStore, data: dict[str, Any]) -> None:
    if 'global_password' in data:
        store.global_sed_key = data['global_password']
    if 'sed_disks_keys' in data:
        store.disks_keys = data['sed_disks_keys']


def sed_keys(store: KMIPKeyStore) -> dict[str, Any]:
    return {
        'global_password': store.global_sed_key,
        'sed_disks_keys': store.disks_keys,
    }


async def reset_sed_global_password(context: ServiceContext, store: KMIPKeyStore, kmip_uid: str | None) -> None:
    store.global_sed_key = ''
    if kmip_uid:
        try:
            await context.to_thread(delete_kmip_secret_data, context, kmip_uid)
        except Exception as e:
            context.middleware.logger.debug(
                f'Failed to remove password from KMIP server for SED Global key: {e}'
            )


async def reset_sed_disk_password(
    context: ServiceContext, store: KMIPKeyStore, disk_id: str, kmip_uid: str | None,
) -> None:
    store.disks_keys.pop(disk_id, None)
    if kmip_uid:
        try:
            await context.to_thread(delete_kmip_secret_data, context, kmip_uid)
        except Exception as e:
            context.middleware.logger.debug(
                f'Failed to remove password from KMIP server for {disk_id}: {e}'
            )
    await context.middleware.call_hook('kmip.sed_keys_sync')
