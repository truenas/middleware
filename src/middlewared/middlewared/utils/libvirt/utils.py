import os
from typing import Any

from middlewared.plugins.zfs.zvol_utils import zvol_name_to_path
from middlewared.utils.usb import libvirt_usb_name_to_port


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
            if target := device['attributes'].get('target'):
                return os.path.normpath(target)
            return None
        case 'PCI':
            return device['attributes'].get('pptdev')
        case 'GPU':
            return device['attributes'].get('pci_address')
        case 'NIC':
            return device['attributes'].get('mac')
        case 'USB':
            # A port and an ID pair name devices in two different ways, and neither can be
            # translated into the other without probing the host. They are kept in separate
            # namespaces so that a port path can never be mistaken for an ID pair.
            if port := device['attributes'].get('port'):
                return f'port:{port}'
            usb = device['attributes'].get('usb')
            if usb and usb.get('vendor_id') and usb.get('product_id'):
                return f'ids:{usb["vendor_id"].lower()}:{usb["product_id"].lower()}'
            return None
        case _:
            return None


def normalize_device_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """Fold a legacy USB ``device`` key from an update payload into ``port``.

    Update payloads are typed as a plain dict, so they bypass the API version adapter. Without
    this, a `device` key sent by an older client would be merged straight into the stored row.
    """
    if attributes.get('dtype') == 'USB' and 'device' in attributes:
        device = attributes.pop('device')
        if device is None:
            # A null `device` is how an older client says "this is no longer identified by a
            # port". The key has to be nulled out explicitly, otherwise the stored port
            # survives the merge and collides with whatever identity is being set instead.
            attributes['port'] = None
        elif not attributes.get('port'):
            attributes['port'] = libvirt_usb_name_to_port(device)

    return attributes


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
