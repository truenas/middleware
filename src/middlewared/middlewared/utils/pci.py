import os

import pyudev
from truenas_pylibvirt.utils.iommu import get_iommu_groups_info, get_pci_device_class, SENSITIVE_PCI_DEVICE_TYPES


def get_pci_device_default_data() -> dict:
    return {
        'capability': {
            'class': None,
            'domain': None,
            'bus': None,
            'slot': None,
            'function': None,
            'product': 'Not Available',
            'vendor': 'Not Available',
        },
        'controller_type': None,
        'critical': False,
        'iommu_group': {},
        'drivers': [],
        'error': None,
        'device_path': None,
        'reset_mechanism_defined': False,
        'description': '',
    }


def get_pci_device_details(obj: pyudev.Device, iommu_info: dict) -> dict:
    data = get_pci_device_default_data()
    if not (igi := iommu_info.get(obj.sys_name)):
        data['error'] = 'Unable to determine iommu group'

    dbs, func = obj.sys_name.split('.')
    dom, bus, slot = dbs.split(':')
    device_path = os.path.join('/sys/bus/pci/devices', obj.sys_name)
    cap_class = f'{(obj.attributes.get("class") or b"").decode()}' or get_pci_device_class(device_path)
    controller_type = obj.properties.get('ID_PCI_SUBCLASS_FROM_DATABASE') or SENSITIVE_PCI_DEVICE_TYPES.get(
        cap_class[:6]
    )

    drivers = []
    if driver := obj.properties.get('DRIVER'):
        drivers.append(driver)

    # Use critical information from iommu_info if available
    data['critical'] = igi['critical'] if igi else True
    data['capability'].update({
        'class': cap_class or None,
        'domain': f'{int(dom, base=16)}',
        'bus': f'{int(bus, base=16)}',
        'slot': f'{int(slot, base=16)}',
        'function': f'{int(func, base=16)}',
        'product': obj.properties.get('ID_MODEL_FROM_DATABASE', 'Not Available'),
        'vendor': obj.properties.get('ID_VENDOR_FROM_DATABASE', 'Not Available'),
    })
    data.update({
        'controller_type': controller_type,
        'iommu_group': igi,
        'drivers': drivers,
        'device_path': device_path,
        'reset_mechanism_defined': os.path.exists(os.path.join(device_path, 'reset')),
    })

    prefix = obj.sys_name + (f' {controller_type!r}' if controller_type else '')
    vendor = data['capability']['vendor'].strip()
    suffix = data['capability']['product'].strip()
    if vendor and suffix:
        data['description'] = f'{prefix}: {suffix} by {vendor!r}'
    else:
        data['description'] = prefix

    return data


def get_all_pci_devices_details() -> dict:
    result = dict()
    iommu_info = get_iommu_groups_info(get_critical_info=True)
    for i in pyudev.Context().list_devices(subsystem='pci'):
        result[i.sys_name] = get_pci_device_details(i, iommu_info)
    return result
