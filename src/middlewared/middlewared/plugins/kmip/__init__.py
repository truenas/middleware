# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api import api_method
from middlewared.api.current import (
    KMIPClearSyncPendingKeysArgs,
    KMIPClearSyncPendingKeysResult,
    KMIPEntry,
    KMIPKmipSyncPendingArgs,
    KMIPKmipSyncPendingResult,
    KMIPSyncKeysArgs,
    KMIPSyncKeysResult,
    KMIPUpdate,
    KMIPUpdateArgs,
    KMIPUpdateResult,
)
from middlewared.service import GenericConfigService, job, periodic, private
from middlewared.service.decorators import pass_thread_local_storage

from . import sed_keys as sed_mod
from . import sync as sync_mod
from . import zfs_keys as zfs_mod
from .config import KMIPConfigServicePart
from .keystore import KMIPKeyStore

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ('KMIPService',)


class KMIPService(GenericConfigService[KMIPEntry]):

    class Config:
        cli_namespace = 'system.kmip'
        entry = KMIPEntry
        generic = True
        role_prefix = 'KMIP'

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._store = KMIPKeyStore()
        self._svc_part = KMIPConfigServicePart(self.context)

    @api_method(KMIPUpdateArgs, KMIPUpdateResult, check_annotations=True)
    @job(lock='kmip_update')
    async def do_update(self, job: Job, data: KMIPUpdate) -> KMIPEntry:
        """
        Update KMIP Server Configuration.

        The system authenticates to the remote KMIP server with a TLS handshake and synchronizes ZFS/SED keys
        between the local database and the server according to the configuration.
        """
        return await self._svc_part.do_update(job, data)

    @api_method(KMIPKmipSyncPendingArgs, KMIPKmipSyncPendingResult, roles=['KMIP_READ'], check_annotations=True)
    async def kmip_sync_pending(self) -> bool:
        """
        Returns true or false based on if there are keys which are to be synced from local database to remote KMIP
        server or vice versa.
        """
        return await self.context.to_thread(sync_mod.kmip_sync_pending, self.context, self._store)

    @periodic(interval=86400)
    @api_method(KMIPSyncKeysArgs, KMIPSyncKeysResult, roles=['KMIP_WRITE'], check_annotations=True)
    async def sync_keys(self) -> None:
        """
        Sync ZFS/SED keys between KMIP Server and TN database.
        """
        await sync_mod.sync_keys(self.context, self._store)

    @api_method(
        KMIPClearSyncPendingKeysArgs, KMIPClearSyncPendingKeysResult, roles=['KMIP_WRITE'], check_annotations=True,
    )
    async def clear_sync_pending_keys(self) -> None:
        """
        Clear all keys which are pending to be synced between KMIP server and TN database.

        For ZFS/SED keys, we remove the UID from local database with which we are able to retrieve ZFS/SED keys.
        It should be used with caution.
        """
        await sync_mod.clear_sync_pending_keys(self.context, self._store)

    @private
    @job(lock='initialize_kmip_keys')
    async def initialize_keys(self, job: Job) -> None:
        await sync_mod.initialize_keys(self.context, self._store, job)

    @private
    async def kmip_memory_keys(self) -> dict[str, Any]:
        return sync_mod.kmip_memory_keys(self._store)

    @private
    async def update_memory_keys(self, data: dict[str, Any]) -> None:
        sync_mod.update_memory_keys(self._store, data)

    @private
    @pass_thread_local_storage
    @job(lock=lambda args: f'kmip_sync_zfs_keys_{args}')
    def sync_zfs_keys(self, job: Job, tls: Any, ids: list[Any] | None = None) -> list[str] | None:
        return zfs_mod.sync_zfs_keys(self.context, self._store, job, tls, ids)

    @private
    @job(lock=lambda args: f'kmip_sync_sed_keys_{args}')
    def sync_sed_keys(self, job: Job, ids: list[Any] | None = None) -> list[str] | None:
        return sed_mod.sync_sed_keys(self.context, self._store, job, ids)

    @private
    async def retrieve_zfs_keys(self) -> dict[str, str]:
        return self._store.zfs_keys

    @private
    async def reset_zfs_key(self, dataset: str, kmip_uid: str | None) -> None:
        await zfs_mod.reset_zfs_key(self.context, self._store, dataset, kmip_uid)

    @private
    async def retrieve_sed_disks_keys(self) -> dict[str, str]:
        return self._store.disks_keys

    @private
    async def sed_global_password(self) -> str:
        return self._store.global_sed_key

    @private
    async def reset_sed_global_password(self, kmip_uid: str | None) -> None:
        await sed_mod.reset_sed_global_password(self.context, self._store, kmip_uid)

    @private
    async def reset_sed_disk_password(self, disk_id: str, kmip_uid: str | None) -> None:
        await sed_mod.reset_sed_disk_password(self.context, self._store, disk_id, kmip_uid)


async def initialize_kmip_keys(middleware: Middleware) -> None:
    if (await middleware.call2(middleware.services.kmip.config)).enabled:
        await middleware.call2(middleware.services.kmip.initialize_keys)


async def __event_system_ready(middleware: Middleware, event_type: str, args: Any) -> None:
    await initialize_kmip_keys(middleware)


async def setup(middleware: Middleware) -> None:
    await middleware.call('network.general.register_activity', 'kmip', 'KMIP')
    middleware.event_subscribe('system.ready', __event_system_ready)
    if await middleware.call('system.ready'):
        await initialize_kmip_keys(middleware)
