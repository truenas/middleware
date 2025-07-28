import collections
import contextlib
import os.path
import pathlib
import re


RE_DEVICE_NAME = re.compile(r'(\w+):(\w+):(\w+).(\w+)')
# get capability classes for relevant pci devices from
# https://github.com/pciutils/pciutils/blob/3d2d69cbc55016c4850ab7333de8e3884ec9d498/lib/header.h#L1429
SENSITIVE_PCI_DEVICE_TYPES = {
    '0x0604': 'PCI Bridge',
    '0x0601': 'ISA Bridge',
    '0x0500': 'RAM memory',
    '0x0c05': 'SMBus',
    '0x0600': 'Host bridge',
}

# Internal numeric mapping for efficient comparisons
_SENSITIVE_PCI_CLASS_CODES_NUMERIC = {
    int(k, 16): v for k, v in SENSITIVE_PCI_DEVICE_TYPES.items()
}


def read_sysfs_hex(path: str, default: int = 0) -> int:
    """Read a hex value from sysfs file."""
    try:
        with open(path, 'r') as f:
            return int(f.read().strip(), 16)
    except (FileNotFoundError, ValueError):
        return default


def get_pci_device_class(pci_path: str) -> str:
    """Get PCI device class as a hex string."""
    with contextlib.suppress(FileNotFoundError):
        with open(os.path.join(pci_path, 'class'), 'r') as r:
            return r.read().strip()
    return ''


def build_pci_device_cache() -> tuple[dict[str, int], dict[tuple[int, int], list[str]]]:
    """
    Build efficient caches for PCI device information.
    Returns:
        Tuple of:
        - device_to_class: Mapping of device address to class code
        - bus_to_devices: Mapping of (domain, bus) tuple to list of device addresses
    """
    device_to_class = {}
    bus_to_devices = collections.defaultdict(list)
    pci_devices_path = pathlib.Path('/sys/bus/pci/devices')
    if pci_devices_path.exists():
        for device_path in pci_devices_path.iterdir():
            if device_path.is_dir() and RE_DEVICE_NAME.fullmatch(device_path.name):
                device_addr = device_path.name
                # Cache class code
                device_to_class[device_addr] = read_sysfs_hex(os.path.join(str(device_path), 'class'))
                # Extract domain and bus number for mapping
                with contextlib.suppress(IndexError, ValueError):
                    parts = device_addr.split(':')
                    domain = int(parts[0], 16)
                    bus = int(parts[1], 16)
                    bus_to_devices[(domain, bus)].append(device_addr)

    return device_to_class, bus_to_devices


def get_bridge_bus_range(bridge_path: str) -> tuple[int, int]:
    """
    Get the secondary and subordinate bus numbers for a PCI bridge.
    Returns:
        Tuple of (secondary_bus, subordinate_bus) or (-1, -1) if not found
    """
    # Note: These sysfs files contain decimal numbers as ASCII strings, not hex
    try:
        with open(os.path.join(bridge_path, 'secondary_bus_number'), 'r') as f:
            secondary = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        secondary = -1

    try:
        with open(os.path.join(bridge_path, 'subordinate_bus_number'), 'r') as f:
            subordinate = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        subordinate = -1

    return secondary, subordinate


def get_devices_behind_bridge(
    bridge_addr: str,
    bus_to_devices: dict[tuple[int, int], list[str]] = None,
) -> list[str]:
    """
    Get all PCI devices behind a specific PCI bridge using proper bus ranges.
    Args:
        bridge_addr: PCI address of the bridge
        bus_to_devices: Optional pre-built bus mapping
    Returns:
        List of PCI addresses behind the bridge (excluding the bridge itself)
    """
    if bus_to_devices is None:
        _, bus_to_devices = build_pci_device_cache()

    bridge_path = f'/sys/bus/pci/devices/{bridge_addr}'
    secondary_bus, subordinate_bus = get_bridge_bus_range(bridge_path)
    if secondary_bus == -1 or subordinate_bus == -1:
        return []

    # Extract bridge domain for proper lookup
    try:
        bridge_domain = int(bridge_addr.split(':')[0], 16)
    except (IndexError, ValueError):
        return []

    # Collect all devices on buses within the bridge's range
    devices_behind = []
    for bus in range(secondary_bus, subordinate_bus + 1):
        devices_behind.extend(bus_to_devices.get((bridge_domain, bus), []))

    # Filter out the bridge itself
    devices_behind = [dev for dev in devices_behind if dev != bridge_addr]
    return devices_behind


def is_pci_bridge_critical(
    bridge_addr: str,
    device_to_class: dict[str, int] = None,
    bus_to_devices: dict[tuple[int, int], list[str]] = None
) -> bool:
    """
    Check if a PCI bridge has critical devices behind it.
    Args:
        bridge_addr: PCI address of the bridge
        device_to_class: Optional pre-built device class mapping
        bus_to_devices: Optional pre-built bus mapping
    Returns:
        True if bridge has critical devices behind it
    """
    if device_to_class is None or bus_to_devices is None:
        device_to_class, bus_to_devices = build_pci_device_cache()

    # Use internal recursive function with visited set for cycle detection
    visited = set()
    return _is_bridge_critical_recursive(
        bridge_addr, device_to_class, bus_to_devices, visited
    )


def _is_bridge_critical_recursive(
    bridge_addr: str,
    device_to_class: dict[str, int],
    bus_to_devices: dict[tuple[int, int], list[str]],
    visited: set[str]
) -> bool:
    """Recursively check if a bridge has critical devices behind it."""
    if bridge_addr in visited:
        return False

    visited.add(bridge_addr)
    devices_behind = get_devices_behind_bridge(bridge_addr, bus_to_devices)
    for device_addr in devices_behind:
        class_code = device_to_class.get(device_addr, 0)
        class_id = (class_code >> 8) & 0xFFFF  # Extract 16-bit class ID
        # Check if it's a critical device type (excluding PCI bridges)
        if class_id in _SENSITIVE_PCI_CLASS_CODES_NUMERIC and class_id != 0x0604:
            return True
        # If it's another bridge, recursively check
        if class_id == 0x0604:
            if _is_bridge_critical_recursive(
                device_addr, device_to_class, bus_to_devices, visited
            ):
                return True
    return False


def get_iommu_groups_info(get_critical_info: bool = False) -> dict[str, dict]:
    addresses = collections.defaultdict(list)
    final = dict()
    with contextlib.suppress(FileNotFoundError):
        # First pass: collect all devices and their classes
        for i in pathlib.Path('/sys/kernel/iommu_groups').glob('*/devices/*'):
            if not i.is_dir() or not i.parent.parent.name.isdigit() or not RE_DEVICE_NAME.fullmatch(i.name):
                continue
            iommu_group = int(i.parent.parent.name)
            dbs, func = i.name.split('.')
            dom, bus, slot = dbs.split(':')
            addresses[iommu_group].append({
                'domain': f'0x{dom}',
                'bus': f'0x{bus}',
                'slot': f'0x{slot}',
                'function': f'0x{func}',
            })
            final[i.name] = {
                'number': iommu_group,
                'addresses': addresses[iommu_group],
            }
            if get_critical_info:
                # Build efficient caches upfront if we need critical info
                device_to_class, bus_to_devices = build_pci_device_cache()
                # Get device class from cache
                class_code = device_to_class.get(i.name, 0)
                class_id = (class_code >> 8) & 0xFFFF  # Extract 16-bit class ID
                # Initially mark as critical based on device type
                is_critical = False
                # Check if it's a sensitive device type
                if class_id in _SENSITIVE_PCI_CLASS_CODES_NUMERIC:
                    if class_id == 0x0604:  # PCI Bridge - needs special handling
                        # Only mark bridge as critical if it has critical devices behind it
                        is_critical = is_pci_bridge_critical(i.name, device_to_class, bus_to_devices)
                    else:
                        # All other sensitive types are always critical
                        is_critical = True
                final[i.name]['critical'] = is_critical
    return final
