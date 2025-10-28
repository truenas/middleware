from truenas_pylibvirt.utils.usb import get_all_usb_devices, find_usb_device_by_libvirt_name

from middlewared.api import api_method
from middlewared.api.current import (
    VMDeviceUsbPassthroughDeviceArgs, VMDeviceUsbPassthroughDeviceResult, VMDeviceUsbPassthroughChoicesArgs,
    VMDeviceUsbPassthroughChoicesResult, VMDeviceUsbControllerChoicesArgs, VMDeviceUsbControllerChoicesResult,
)
from middlewared.service import Service
from middlewared.utils.libvirt.usb import USB_CONTROLLER_CHOICES


class VMDeviceService(Service):

    class Config:
        namespace = 'vm.device'

    @api_method(VMDeviceUsbControllerChoicesArgs, VMDeviceUsbControllerChoicesResult, roles=['VM_DEVICE_READ'])
    async def usb_controller_choices(self):
        """
        Retrieve USB controller type choices
        """
        return {k: k for k in USB_CONTROLLER_CHOICES}

    @api_method(VMDeviceUsbPassthroughDeviceArgs, VMDeviceUsbPassthroughDeviceResult, roles=['VM_DEVICE_READ'])
    def usb_passthrough_device(self, device):
        """
        Retrieve details about `device` USB device.
        """
        return find_usb_device_by_libvirt_name(device)

    @api_method(
        VMDeviceUsbPassthroughChoicesArgs, VMDeviceUsbPassthroughChoicesResult, roles=['VM_DEVICE_READ']
    )
    def usb_passthrough_choices(self):
        """
        Available choices for USB passthrough devices.
        """
        return get_all_usb_devices()
