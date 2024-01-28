import contextlib
import os
import shutil

from middlewared.plugins.zfs_.utils import zvol_path_to_name


DEFAULT_NVRAM_FOLDER_PATH = '/var/lib/libvirt/qemu/nvram'
LIBVIRT_QEMU_UID = 64055
LIBVIRT_QEMU_GID = 64055


def get_root_ds_from_disk_device(disk_device):
    with contextlib.suppress(ValueError):
        return zvol_path_to_name(disk_device['attributes']['path']).split('/')[0]


def migrate(middleware):
    existing_nvram_files = os.listdir(DEFAULT_NVRAM_FOLDER_PATH)
    existing_root_datasets = [
        ds['id'] for ds in middleware.call_sync(
            'pool.dataset.query', [], {'extra': {'properties': ['name'], 'retrieve_children': False}}
        )
    ]
    default_ds_to_use = existing_root_datasets[0] if existing_root_datasets else None
    for vm in middleware.call_sync('vm.query', [['bootloader', '=', 'UEFI'], ['nvram_location', '=', None]]):
        try:
            migrate_vm_nvram_file(middleware, existing_nvram_files, vm, default_ds_to_use)
        except Exception:
            middleware.logger.error('Failed to migrate nvram file for VM %r(%r)', vm['name'], vm['id'], exc_info=True)


def migrate_vm_nvram_file(middleware, existing_nvram_files, vm, default_ds_to_use):
    file_name = f'{vm["id"]}_{vm["name"]}_VARS.fd'
    root_ds_to_use = default_ds_to_use
    for disk_device in middleware.call_sync('vm.device.query', [['vm', '=', vm['id']], ['dtype', '=', 'DISK']]):
        if root_ds := get_root_ds_from_disk_device(disk_device):
            root_ds_to_use = root_ds
            break

    # We will copy the file here if it exists and update the nvram_location
    if root_ds_to_use:
        new_path = os.path.join('/mnt', root_ds_to_use, file_name)
        i = 2
        while True:
            if not os.path.exists(new_path):
                break
            new_path = os.path.join('/mnt', root_ds_to_use, f'{file_name}_{i}')
            i += 1

        if file_name in existing_nvram_files:
            to_copy_path = os.path.join(DEFAULT_NVRAM_FOLDER_PATH, file_name)
            shutil.copy(to_copy_path, new_path)
            shutil.copystat(to_copy_path, new_path)
            os.chown(new_path, LIBVIRT_QEMU_UID, LIBVIRT_QEMU_GID)
        else:
            # File does not exist for us to copy, so we need to log an error here and still specify a path
            # as libvirt will create this file now on it's own which should be fine
            middleware.logger.error(
                'No nvram file found for VM %r(%r), hence setting it up with %r', vm['name'], vm['id'], new_path
            )

        middleware.call_sync('datastore.update', 'vm.vm', vm['id'], {'nvram_location': new_path})

    else:
        # Log an error here for the VM in question as it means there are no pools available
        middleware.logger.error('There is no pool to setup nvram file for VM %r(%r)', vm['name'], vm['id'])
