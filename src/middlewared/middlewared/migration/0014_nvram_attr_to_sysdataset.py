import os
import shutil

from middlewared.plugins.vm.utils import LIBVIRT_QEMU_UID, LIBVIRT_QEMU_GID


OLD_NVRAM_FOLDER_PATH = '/data/subsystems/vm/nvram'
NEW_NVRAM_FOLDER_PATH = '/var/db/system/vm/nvram'


def migrate(middleware):
    """
    Migrate VM NVRAM files from old location (/data/subsystems/vm/nvram) to
    new system dataset location (/var/db/system/vm/nvram).

    This migration keeps the old files intact for backup purposes.
    """
    if middleware.call_sync('system.is_ha_capable'):
        middleware.logger.debug(
            'Skipping nvram migration to system dataset as system is HA capable'
        )
        return

    # Check if old path exists and has files
    if not os.path.exists(OLD_NVRAM_FOLDER_PATH):
        middleware.logger.debug(
            'Old NVRAM folder path %r does not exist, nothing to migrate',
            OLD_NVRAM_FOLDER_PATH
        )
        return

    # Ensure system dataset is properly mounted
    sysdataset_path = middleware.call_sync('systemdataset.sysdataset_path')
    if not sysdataset_path:
        middleware.logger.warning('System dataset is not mounted, skipping NVRAM migration')
        return

    # Create new nvram directory if it doesn't exist
    # The parent /var/db/system/vm should already exist from
    # system dataset mount
    if not os.path.exists(NEW_NVRAM_FOLDER_PATH):
        try:
            os.makedirs(NEW_NVRAM_FOLDER_PATH, exist_ok=True)
            os.chown(NEW_NVRAM_FOLDER_PATH, LIBVIRT_QEMU_UID, LIBVIRT_QEMU_GID)
        except Exception as e:
            middleware.logger.error(
                'Failed to create new NVRAM folder path: %s', e
            )
            return

    # Get list of NVRAM files to migrate
    try:
        nvram_files = [f for f in os.listdir(OLD_NVRAM_FOLDER_PATH) if f.endswith('_VARS.fd')]
    except Exception as e:
        middleware.logger.error(
            'Failed to list files in old NVRAM folder: %s', e
        )
        return

    if not nvram_files:
        middleware.logger.debug('No NVRAM files found to migrate')
        return

    # Copy each NVRAM file to new location
    migrated_count = 0
    for nvram_file in nvram_files:
        old_path = os.path.join(OLD_NVRAM_FOLDER_PATH, nvram_file)
        new_path = os.path.join(NEW_NVRAM_FOLDER_PATH, nvram_file)

        try:
            # Skip if file already exists in new location
            if os.path.exists(new_path):
                middleware.logger.debug('NVRAM file %r already exists in new location, skipping', nvram_file)
                continue

            # Copy file to new location
            shutil.copy2(old_path, new_path)
            # Set proper ownership
            os.chown(new_path, LIBVIRT_QEMU_UID, LIBVIRT_QEMU_GID)
            migrated_count += 1
            middleware.logger.debug('Successfully migrated NVRAM file %r', nvram_file)
        except Exception as e:
            middleware.logger.error('Failed to migrate NVRAM file %r: %s', nvram_file, e)

    middleware.logger.info('Migrated %d NVRAM files to system dataset', migrated_count)
