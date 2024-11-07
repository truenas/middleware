from xml.etree import ElementTree as etree


ACTIVE_STATES = ['RUNNING', 'SUSPENDED']
SYSTEM_NVRAM_FOLDER_PATH = '/data/subsystems/vm/nvram'
LIBVIRT_QEMU_UID = 986
LIBVIRT_QEMU_GID = 986
LIBVIRT_URI = 'qemu+unix:///system?socket=/run/truenas_libvirt/libvirt-sock'
LIBVIRT_USER = 'libvirt-qemu'
NGINX_PREFIX = '/vm/display'


def create_element(*args, **kwargs):
    attribute_dict = kwargs.pop('attribute_dict', {})
    element = etree.Element(*args, **kwargs)
    element.text = attribute_dict.get('text')
    element.tail = attribute_dict.get('tail')
    for child in attribute_dict.get('children', []):
        element.append(child)
    return element


def get_virsh_command_args():
    return ['virsh', '-c', LIBVIRT_URI]


def convert_pci_id_to_vm_pci_slot(pci_id: str) -> str:
    return f'pci_{pci_id.replace(".", "_").replace(":", "_")}'


def get_vm_nvram_file_name(vm_data: dict) -> str:
    return f'{vm_data["id"]}_{vm_data["name"]}_VARS.fd'


def get_default_status() -> dict:
    return {
        'state': 'ERROR',
        'pid': None,
        'domain_state': 'ERROR',
    }
