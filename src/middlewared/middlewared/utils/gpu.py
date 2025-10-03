import collections
import os
import re
from typing import TextIO

import pyudev
from truenas_pylibvirt.utils.iommu import build_pci_device_cache, get_iommu_groups_info, GPU_CLASS_CODES


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


def _get_gpu_description(gpu_dev: pyudev.Device, controller_type: str) -> str:
    """
    Get GPU description from pyudev device.
    Args:
        gpu_dev: pyudev Device object
        controller_type: Device type string (e.g., 'VGA compatible controller')
    Returns:
        GPU description string
    """
    vendor = gpu_dev.get('ID_VENDOR_FROM_DATABASE', '')
    model = gpu_dev.get('ID_MODEL_FROM_DATABASE', '')

    if vendor and model:
        return f"{vendor} {model}"
    elif model:
        return model
    elif vendor:
        return f"{vendor} {controller_type}"
    else:
        return controller_type


def get_critical_devices_in_iommu_group_mapping(iommu_groups: dict) -> dict[str, set[str]]:
    iommu_groups_mapping_with_critical_devices = collections.defaultdict(set)
    for pci_slot, pci_details in iommu_groups.items():
        if pci_details['critical']:
            iommu_groups_mapping_with_critical_devices[pci_details['number']].add(pci_slot)
    return iommu_groups_mapping_with_critical_devices


def get_gpus() -> list:
    # Build PCI device cache once
    device_to_class, bus_to_devices = build_pci_device_cache()

    # Find all GPU devices by class code
    gpu_slots = []
    for device_addr, class_code in device_to_class.items():
        class_id = (class_code >> 8) & 0xFFFF  # Extract 16-bit class ID
        if class_id in GPU_CLASS_CODES:
            gpu_slots.append((device_addr, GPU_CLASS_CODES[class_id]))

    gpus = []
    iommu_groups = get_iommu_groups_info(get_critical_info=True, pci_build_cache=(device_to_class, bus_to_devices))
    # Precompute group_id -> [devices] mapping for efficiency
    group_to_devices = collections.defaultdict(list)
    for device_addr, device_info in iommu_groups.items():
        group_to_devices[device_info['number']].append(device_addr)

    udev_context = pyudev.Context()
    for addr, controller_type in gpu_slots:
        addr_re = RE_PCI_ADDR.match(addr)
        gpu_dev = pyudev.Devices.from_name(udev_context, 'pci', addr)
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
        critical_devices = []
        # Get the GPU's IOMMU group number
        gpu_iommu_group = iommu_groups.get(addr, {}).get('number')
        # Get all devices in the same IOMMU group as the GPU (using precomputed mapping)
        devices_in_group = group_to_devices.get(gpu_iommu_group, []) if gpu_iommu_group is not None else []
        # Process each device in the same IOMMU group
        for device_addr in devices_in_group:
            try:
                # Get device information
                device = pyudev.Devices.from_name(udev_context, 'pci', device_addr)
                pci_id = device.get('PCI_ID', '')
                subclass = device.get('ID_PCI_SUBCLASS_FROM_DATABASE', '')
                model = device.get('ID_MODEL_FROM_DATABASE', '')
                # Add to devices list
                devices.append({
                    'pci_id': pci_id,
                    'pci_slot': device_addr,
                    'vm_pci_slot': f'pci_{device_addr.replace(".", "_").replace(":", "_")}',
                })
                # Check if this device is critical
                if iommu_groups.get(device_addr, {}).get('critical', False):
                    device_desc = get_pci_device_description(device_addr, subclass, model)
                    critical_devices.append(device_desc)
            except (OSError, IOError, ValueError):
                # If we can't get device info due to permission or I/O issues,
                # still add it to the list with minimal information
                devices.append({
                    'pci_id': '',
                    'pci_slot': device_addr,
                    'vm_pci_slot': f'pci_{device_addr.replace(".", "_").replace(":", "_")}',
                })

        # Build critical reason if there are critical devices in the group
        if critical_devices:
            device_list = ', '.join(critical_devices)
            critical_reason = f'Devices sharing memory management: {device_list}'
        gpus.append({
            'addr': {
                'pci_slot': addr,
                **{k: addr_re.group(k) for k in ('domain', 'bus', 'slot')},
            },
            'description': _get_gpu_description(gpu_dev, controller_type),
            'devices': devices,
            'vendor': vendor,
            'uses_system_critical_devices': bool(critical_reason),
            'critical_reason': critical_reason,
        })
    return gpus
