import os
import shutil

from middlewared.plugins.vm.utils import get_vm_nvram_file_name, LIBVIRT_QEMU_UID, LIBVIRT_QEMU_GID


DEFAULT_NVRAM_FOLDER_PATH = '/var/lib/libvirt/qemu/nvram'
SYSTEM_NVRAM_FOLDER_PATH_OLD_DATA = '/data/subsystems/vm/nvram'


def migrate(middleware):
    os.makedirs(SYSTEM_NVRAM_FOLDER_PATH_OLD_DATA, exist_ok=True)
    os.chown(SYSTEM_NVRAM_FOLDER_PATH_OLD_DATA, LIBVIRT_QEMU_UID, LIBVIRT_QEMU_GID)

    if middleware.call_sync('system.is_ha_capable'):
        middleware.logger.debug('Skipping nvram migration as system is HA capable')
        return

    for vm in middleware.call_sync('vm.query', [['bootloader', '=', 'UEFI']]):
        try:
            migrate_vm_nvram_file(middleware, vm)
        except Exception:
            middleware.logger.error('Failed to migrate nvram file for VM %r(%r)', vm['name'], vm['id'], exc_info=True)


def migrate_vm_nvram_file(middleware, vm):
    file_name = get_vm_nvram_file_name(vm)
    new_path = os.path.join(SYSTEM_NVRAM_FOLDER_PATH_OLD_DATA, file_name)
    to_copy_path = os.path.join(DEFAULT_NVRAM_FOLDER_PATH, file_name)
    if os.path.exists(to_copy_path):
        shutil.copy2(to_copy_path, new_path)
        os.chown(new_path, LIBVIRT_QEMU_UID, LIBVIRT_QEMU_GID)
    else:
        # File does not exist for us to copy, so we need to just log it
        middleware.logger.debug(
            'No nvram file found for VM %r(%r), hence setting it up with %r', vm['name'], vm['id'], new_path
        )
