import collections
import os
import re
import subprocess
from typing import TextIO

import pyudev

from middlewared.service_exception import CallError
from .iommu import get_iommu_groups_info
from .pci import SENSITIVE_PCI_DEVICE_TYPES


RE_PCI_ADDR = re.compile(r'(?P<domain>.*):(?P<bus>.*):(?P<slot>.*)\.')


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
        critical_devices = set()

        # So we will try to mark those gpu's as critical which meet following criteria:
        # 1) Have a device which belongs to sensitive pci devices group
        # 2) Have a device which is in same iommu group as a device which belongs to sensitive pci devices group
        if critical_iommu_mapping[iommu_groups.get(addr, {}).get('number')]:
            critical_devices_based_on_iommu = {addr}
        else:
            critical_devices_based_on_iommu = set()

        for child in filter(lambda c: all(k in c for k in ('PCI_SLOT_NAME', 'PCI_ID')), gpu_dev.parent.children):
            devices.append({
                'pci_id': child['PCI_ID'],
                'pci_slot': child['PCI_SLOT_NAME'],
                'vm_pci_slot': f'pci_{child["PCI_SLOT_NAME"].replace(".", "_").replace(":", "_")}',
            })
            for k in SENSITIVE_PCI_DEVICE_TYPES.values():
                if k.lower() in child.get('ID_PCI_SUBCLASS_FROM_DATABASE', '').lower():
                    critical_devices.add(child['PCI_SLOT_NAME'])
                    break
            if critical_iommu_mapping[iommu_groups.get(child['PCI_SLOT_NAME'], {}).get('number')]:
                critical_devices_based_on_iommu.add(child['PCI_SLOT_NAME'])

        if critical_devices:
            critical_reason = f'Critical devices found: {", ".join(critical_devices)}'

        if critical_devices_based_on_iommu:
            critical_reason = f'{critical_reason}\n' if critical_reason else ''
            critical_reason += ('Critical devices found in same IOMMU group: '
                                f'{", ".join(critical_devices_based_on_iommu)}')

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
