import collections
import os
import re
import subprocess
from typing import TextIO

import pyudev

from middlewared.service_exception import CallError
from .iommu import get_iommu_groups_info, SENSITIVE_PCI_DEVICE_TYPES


RE_PCI_ADDR = re.compile(r'(?P<domain>.*):(?P<bus>.*):(?P<slot>.*)\.')


def get_pci_device_description(pci_slot: str, subclass: str = None, model: str = None) -> str:
    """
    Get human-readable device description with PCI slot.
    Uses caching to avoid repeated lookups for the same device.

    Args:
        pci_slot: PCI slot address (e.g., "0000:00:1f.4")
        subclass: ID_PCI_SUBCLASS_FROM_DATABASE value
        model: ID_MODEL_FROM_DATABASE value

    Returns:
        Human-readable description like "SMBus (0000:00:1f.4)"
    """
    if model and model != 'Not Available':
        return f'{model} ({pci_slot})'
    elif subclass:
        return f'{subclass} ({pci_slot})'
    else:
        return pci_slot


def parse_nvidia_info_file(file_obj: TextIO) -> tuple[dict, str]:
    gpu, bus_loc = dict(), None
    for line in file_obj:
        k, v = line.split(':', 1)
        k, v = k.strip().lower().replace(' ', '_'), v.strip()
        gpu[k] = v
        if k == 'bus_location':
            bus_loc = v
    return gpu, bus_loc


def get_nvidia_gpus() -> dict[str, dict]:
    """Don't be so complicated. Return basic information about
    NVIDIA devices (if any) that are connected."""
    gpus = dict()
    try:
        with os.scandir('/proc/driver/nvidia/gpus') as gdir:
            for i in filter(lambda x: x.is_dir(), gdir):
                with open(os.path.join(i.path, 'information'), 'r') as f:
                    gpu, bus_location = parse_nvidia_info_file(f)
                    if bus_location is not None:
                        gpus[bus_location] = gpu
                    elif gpu:
                        # maybe a line in the file changed but
                        # we still got some information, just use
                        # the procfs dirname as the key (which is
                        # unique per gpu)
                        gpus[i.name] = gpu
    except (FileNotFoundError, ValueError):
        pass

    return gpus


def get_critical_devices_in_iommu_group_mapping(iommu_groups: dict) -> dict[str, set[str]]:
    iommu_groups_mapping_with_critical_devices = collections.defaultdict(set)
    for pci_slot, pci_details in iommu_groups.items():
        if pci_details['critical']:
            iommu_groups_mapping_with_critical_devices[pci_details['number']].add(pci_slot)

    return iommu_groups_mapping_with_critical_devices


def get_gpus() -> list:
    cp = subprocess.Popen(['lspci', '-D'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = cp.communicate()
    if cp.returncode:
        raise CallError(f'Unable to list available gpus: {stderr.decode()}')

    gpus = []
    gpu_slots = []
    for line in stdout.decode().splitlines():
        for k in (
            'VGA compatible controller',
            'Display controller',
            '3D controller',
        ):
            if k in line:
                gpu_slots.append((line.strip(), k))
                break

    iommu_groups = get_iommu_groups_info(get_critical_info=True)
    critical_iommu_mapping = get_critical_devices_in_iommu_group_mapping(iommu_groups)

    for gpu_line, key in gpu_slots:
        addr = gpu_line.split()[0]
        addr_re = RE_PCI_ADDR.match(addr)

        gpu_dev = pyudev.Devices.from_name(pyudev.Context(), 'pci', addr)
        # Let's normalise vendor for consistency
        vendor = None
        vendor_id_from_db = gpu_dev.get('ID_VENDOR_FROM_DATABASE', '').lower()
        if 'nvidia' in vendor_id_from_db:
            vendor = 'NVIDIA'
        elif 'intel' in vendor_id_from_db:
            vendor = 'INTEL'
        elif 'amd' in vendor_id_from_db:
            vendor = 'AMD'

        devices = []
        critical_reason = None
        critical_devices = {}
        critical_devices_based_on_iommu = {}

        # So we will try to mark those gpu's as critical which meet following criteria:
        # 1) Have a device which belongs to sensitive pci devices group
        # 2) Have a device which is in same iommu group as a device which belongs to sensitive pci devices group

        # Check if the GPU itself is in a critical IOMMU group
        if critical_iommu_mapping[iommu_groups.get(addr, {}).get('number')]:
            # Get GPU device info for description
            gpu_subclass = gpu_dev.get('ID_PCI_SUBCLASS_FROM_DATABASE', '')
            gpu_model = gpu_dev.get('ID_MODEL_FROM_DATABASE', '')
            device_desc = get_pci_device_description(addr, gpu_subclass, gpu_model)
            critical_devices_based_on_iommu[addr] = device_desc

        for child in filter(lambda c: all(k in c for k in ('PCI_SLOT_NAME', 'PCI_ID')), gpu_dev.parent.children):
            pci_slot = child['PCI_SLOT_NAME']
            subclass = child.get('ID_PCI_SUBCLASS_FROM_DATABASE', '')
            model = child.get('ID_MODEL_FROM_DATABASE', '')

            devices.append({
                'pci_id': child['PCI_ID'],
                'pci_slot': pci_slot,
                'vm_pci_slot': f'pci_{pci_slot.replace(".", "_").replace(":", "_")}',
            })

            # Check if it's a critical device type
            for k in SENSITIVE_PCI_DEVICE_TYPES.values():
                if k.lower() in subclass.lower():
                    device_desc = get_pci_device_description(pci_slot, subclass, model)
                    critical_devices[pci_slot] = device_desc
                    break

            # Check IOMMU group
            if critical_iommu_mapping[iommu_groups.get(pci_slot, {}).get('number')]:
                device_desc = get_pci_device_description(pci_slot, subclass, model)
                critical_devices_based_on_iommu[pci_slot] = device_desc

        if critical_devices:
            device_list = ', '.join(critical_devices.values())
            critical_reason = f'Devices sharing memory management: {device_list}'

        if critical_devices_based_on_iommu:
            device_list = ', '.join(critical_devices_based_on_iommu.values())
            if critical_reason:
                critical_reason += '\n'
            else:
                critical_reason = ''
            critical_reason += f'Devices sharing memory management in same IOMMU group: {device_list}'

        gpus.append({
            'addr': {
                'pci_slot': addr,
                **{k: addr_re.group(k) for k in ('domain', 'bus', 'slot')},
            },
            'description': gpu_line.split(f'{key}:')[-1].split('(rev')[0].strip(),
            'devices': devices,
            'vendor': vendor,
            'uses_system_critical_devices': bool(critical_reason),
            'critical_reason': critical_reason,
        })

    return gpus
