"""Helpers for USB passthrough device identity.

This module must only import from the standard library. It is shared between an
alembic migration and the API version adapters, and the latter are not allowed
to pull arbitrary middleware code in.
"""
import re
from typing import Any, NamedTuple

# A sysfs USB port path: a bus number, a root port, then one segment per hub
# traversed, e.g. '1-4' or '5-1.1'.
USB_PORT_PATTERN = r'^\d+-\d+(\.\d+)*$'
RE_USB_PORT = re.compile(USB_PORT_PATTERN)

# A USB vendor/product id, in the shape the host reports it and the API accepts it.
USB_ID_PATTERN = r'^0x[0-9a-f]{4}$'
RE_USB_ID = re.compile(USB_ID_PATTERN)

# libvirt names a root hub after its sysfs sys_name, which is 'usbN'.
RE_USB_ROOT_HUB = re.compile(r'^usb_usb\d+$')

RE_HEX = re.compile(r'^[0-9a-fA-F]+$')

DROP_ROOT_HUB = 'it names a USB root hub, which is not a socket a device can be plugged into'
DROP_DEVICE_NUMBER = (
    'it was stored as a bus and device number, which the kernel hands out afresh on every replug, so the '
    'physical port it referred to cannot be worked out without the device in front of us'
)
DROP_NO_IDENTITY = 'it identifies nothing: neither a port nor a vendor/product id was stored'
DROP_BAD_PORT = 'the value stored as its port is not a sysfs port path'
DROP_BAD_USB_ID = 'the value stored as its vendor/product id is not a four digit hexadecimal number'


class MigratedUSBDevice(NamedTuple):
    """The outcome of migrating one USB device's attributes.

    Exactly one of the two is set: `attributes` for a device that survives, and
    `drop_reason` for one whose row has to go because no identity the API can
    read back can be salvaged from it.
    """
    attributes: dict[str, Any] | None
    drop_reason: str | None


def libvirt_usb_name_to_port(value: str) -> str:
    """Convert a libvirt nodedev name such as 'usb_5_1_1' to a port path '5-1.1'.

    Anything that is already a port path, or that does not look like a libvirt
    USB nodedev name, is handed back untouched. This is idempotent on purpose:
    the migration may be re-run, and the UI echoes choices keys straight back.
    """
    value = value.strip()
    if RE_USB_PORT.match(value) or not value.startswith('usb_'):
        return value

    segments = []
    for segment in value[len('usb_'):].split('_'):
        if segment.isdigit():
            # '000' must collapse to '0', not to the empty string.
            segment = segment.lstrip('0') or '0'
        segments.append(segment)

    if len(segments) == 1:
        return segments[0]

    return f'{segments[0]}-{".".join(segments[1:])}'


def normalize_usb_id(value: str) -> str:
    """Render a USB vendor/product id in the canonical lowercase, zero-padded '0x' form.

    An id is four hex digits wide, so anything shorter is padded out to match what
    the host reports and what the API accepts. Anything longer is left as it is
    rather than truncated: it is junk, and losing digits would silently turn it
    into a different, valid-looking id.

    Values that are not hexadecimal are handed back untouched so that callers
    sweeping stored data never blow up on junk.
    """
    body = value.strip()
    while body[:2].lower() == '0x':
        body = body[2:]

    if not RE_HEX.match(body):
        return value

    return f'0x{body.lower().zfill(4)}'


def migrate_usb_device_attributes(
    attributes: dict[str, Any], *, device_is_port_path: bool
) -> MigratedUSBDevice:
    """Rewrite a USB device's ``device`` identity into a ``port`` path.

    `device_is_port_path` says whether a stored `device` value can be read as a
    physical port at all. Where it cannot, the value names a socket we have no
    way of recovering, so the device is dropped rather than silently pointed at
    a different, plausible looking one.

    Returns the new attributes, or the reason the row has to be deleted.
    """
    updated = dict(attributes)

    if 'device' not in updated:
        # Already migrated. Only the ids are worth touching, and only when they
        # need it, so that a caller comparing the result against the input can
        # tell there is nothing to write back.
        if isinstance(updated.get('usb'), dict):
            updated['usb'] = _normalize_usb_ids(updated['usb'])

        return _readable_by_the_api(updated)

    device = updated.pop('device')
    # Anything that is not a string names nothing, so treat it as if `device`
    # had never been set and fall back to whatever else the row carries.
    device = device.strip() if isinstance(device, str) else ''

    if device:
        if RE_USB_ROOT_HUB.match(device):
            # Checked first because it holds however the value is read, and
            # because the transform below would happily turn 'usb_usb1' into
            # 'usb1'.
            return MigratedUSBDevice(None, DROP_ROOT_HUB)

        if not device_is_port_path:
            return MigratedUSBDevice(None, DROP_DEVICE_NUMBER)

    port = updated.get('port')
    if device:
        port = libvirt_usb_name_to_port(device)

    usb = _normalize_usb_ids(updated.get('usb'))
    if port is not None:
        # A port names exactly one socket, which makes the vendor/product pair
        # redundant. This is the precedence the device code already applies.
        usb = None

    updated['port'] = port
    updated['usb'] = usb
    return _readable_by_the_api(updated)


def _readable_by_the_api(updated: dict[str, Any]) -> MigratedUSBDevice:
    """Refuse to hand back a shape the API would go on to reject.

    A row the API cannot parse is worse than no row: it is invisible in the UI,
    cannot be edited or deleted from there, and drags down the reply it appears
    in. Repairing one is not an option either, since there is no way to tell
    which device was meant.
    """
    port = updated.get('port')
    usb = updated.get('usb')

    if port is None and usb is None:
        return MigratedUSBDevice(None, DROP_NO_IDENTITY)

    if port is not None and not (isinstance(port, str) and RE_USB_PORT.match(port)):
        return MigratedUSBDevice(None, DROP_BAD_PORT)

    if usb is not None:
        if not isinstance(usb, dict):
            return MigratedUSBDevice(None, DROP_NO_IDENTITY)

        for key in ('vendor_id', 'product_id'):
            value = usb.get(key)
            if not isinstance(value, str) or not RE_USB_ID.match(value):
                return MigratedUSBDevice(None, DROP_BAD_USB_ID)

    return MigratedUSBDevice(updated, None)


def _normalize_usb_ids(usb: Any) -> Any:
    if not isinstance(usb, dict):
        return usb

    usb = dict(usb)
    for key in ('vendor_id', 'product_id'):
        if isinstance(usb.get(key), str):
            usb[key] = normalize_usb_id(usb[key])

    return usb
