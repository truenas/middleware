import os

from truenas_pylibvirt import VmDomain as BaseVMDomain

from .utils import SYSTEM_NVRAM_FOLDER_PATH, get_vm_nvram_file_name


class VmDomain(BaseVMDomain):

    def nvram_path(self):
        return os.path.join(SYSTEM_NVRAM_FOLDER_PATH, get_vm_nvram_file_name({
            'id': self.configuration.id,
            'name': self.configuration.name,
        }))
