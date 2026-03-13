from __future__ import annotations

from truenas_pylibvirt.utils.usb import find_usb_device_by_libvirt_name, get_all_usb_devices

from middlewared.api.current import USBPassthroughDevice, USBPassthroughInfo
from middlewared.utils.libvirt.usb import USB_CONTROLLER_CHOICES


def usb_controller_choices() -> dict[str, str]:
    return {k: k for k in USB_CONTROLLER_CHOICES}


def usb_passthrough_device(device: str) -> USBPassthroughDevice:
    return USBPassthroughDevice.model_validate(find_usb_device_by_libvirt_name(device))


def usb_passthrough_choices() -> USBPassthroughInfo:
    return USBPassthroughInfo.model_validate(get_all_usb_devices())
