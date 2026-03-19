SYSTEM_TPM_FOLDER_PATH = '/var/db/system/vm/tpm'
SYSTEM_NVRAM_FOLDER_PATH = '/var/db/system/vm/nvram'
LIBVIRT_QEMU_UID = 986
LIBVIRT_QEMU_GID = 986


def get_vm_tpm_state_dir_name(id_: int, name: str) -> str:
    return f'{id_}_{name}_tpm_state'


def get_vm_nvram_file_name(id_: int, name: str) -> str:
    return f'{id_}_{name}_VARS.fd'
