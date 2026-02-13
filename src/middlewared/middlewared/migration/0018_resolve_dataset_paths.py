# -*- coding=utf-8 -*-
"""
Resolve dataset paths for sharing services.

This migration splits filesystem paths into (dataset, relative_path) components
for SMB shares, iSCSI extents, rsync tasks, NVMe-oF namespaces, etc.

Must run after boot when datasets are mounted (unlike alembic migrations which
run before mount). Paths that cannot be resolved (encrypted datasets, hardware
issues) are left as NULL and will be resolved via hook subscriptions when the
datasets become available.
"""
from middlewared.plugins.cloud_backup.crud import CloudBackupService
from middlewared.plugins.cloud_sync import CloudSyncService
from middlewared.plugins.iscsi_.extents import iSCSITargetExtentService
from middlewared.plugins.nfs import SharingNFSService
from middlewared.plugins.nvmet.namespace import NVMetNamespaceService
from middlewared.plugins.rsync import RsyncTaskService
from middlewared.plugins.smb import SharingSMBService
from middlewared.plugins.webshare.sharing import SharingWebshareService


async def migrate(middleware):
    for service in (
        SharingSMBService,
        SharingNFSService,
        SharingWebshareService,
        iSCSITargetExtentService,
        RsyncTaskService,
        CloudBackupService,
        CloudSyncService,
        NVMetNamespaceService,
    ):
        try:
            await service.resolve_paths(middleware)
        except Exception as e:
            middleware.logger.error(f"Error migrating {service._config.namespace}: {e}", exc_info=True)
