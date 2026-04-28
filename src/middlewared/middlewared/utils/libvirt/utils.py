from typing import Any

from truenas_pylibvirt.utils.usb import find_usb_device_by_ids

from middlewared.plugins.zfs.zvol_utils import zvol_name_to_path

ACTIVE_STATES = ('RUNNING', 'SUSPENDED')
LIBVIRT_USER = 'libvirt-qemu'
NGINX_PREFIX = '/vm/display'


def translate_device(dev: dict[str, Any]) -> str:
    # A disk should have a path configured at all times, when that is not the case, that means `dtype` is DISK
    # and end user wants to create a new zvol in this case.
    zvol_name = zvol_name_to_path(dev['attributes']['zvol_name']) if dev['attributes'].get('zvol_name') else None
    return str(dev['attributes'].get('path') or zvol_name or dev['attributes']['target'])


def _extract_identity(device: dict[str, Any]) -> str | None:
    """Extract the unique identity of a device based on its type."""
    match device['attributes']['dtype']:
        case 'DISK' | 'RAW' | 'CDROM':
            return translate_device(device)
        case 'FILESYSTEM':
            return device['attributes'].get('target')
        case 'PCI':
            return device['attributes'].get('pptdev')
        case 'GPU':
            return device['attributes'].get('pci_address')
        case 'NIC':
            return device['attributes'].get('mac')
        case 'USB':
            if device['attributes'].get('device'):
                return device['attributes']['device']
            usb = device['attributes'].get('usb')
            if usb and usb.get('vendor_id') and usb.get('product_id'):
                return find_usb_device_by_ids(usb['vendor_id'], usb['product_id'])
            return None
        case _:
            return None


def device_uniqueness_check(
    device: dict[str, Any],
    instance: dict[str, Any],
    dtype: str | tuple[str, ...],
) -> bool:
    """Check that a device is not already present on the given instance.

    Args:
        device: The device being created or updated.
        instance: The VM/container instance containing all its devices.
        dtype: Device type(s) to filter against (e.g. 'PCI' or ('DISK', 'RAW', 'CDROM', 'FILESYSTEM')).

    Returns:
        True if the device is unique (or identity is None), False if it's a duplicate.
    """
    identity = _extract_identity(device)
    if identity is None:
        return True

    if isinstance(dtype, str):
        dtype = (dtype,)

    matches = [
        d for d in instance['devices']
        if d['attributes']['dtype'] in dtype and _extract_identity(d) == identity
    ]
    if not matches:
        # No device with this identity exists on the instance
        return True
    elif len(matches) > 1:
        # Instance is mis-configured
        return False
    elif not device.get('id') and matches:
        # A new device is being created, however it already exists in instance. This can also happen when instance
        # is being created, in that case it's okay. Key here is that we won't have the id field present
        return not bool(matches[0].get('id'))
    elif device.get('id'):
        # The device is being updated, if the device is same as we have in db, we are okay
        return bool(device['id'] == matches[0].get('id'))
    else:
        return False
