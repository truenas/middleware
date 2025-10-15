SYSTEM_NVRAM_FOLDER_PATH = '/var/db/system/vm/nvram'
LIBVIRT_QEMU_UID = 986
LIBVIRT_QEMU_GID = 986


def get_vm_nvram_file_name(vm_data: dict) -> str:
    return f'{vm_data["id"]}_{vm_data["name"]}_VARS.fd'
