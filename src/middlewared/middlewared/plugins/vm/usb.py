from typing import get_args

from truenas_pylibvirt.utils.usb import get_all_usb_devices, USBInventory

from middlewared.api import api_method
from middlewared.api.current import (
    VMDeviceUsbPassthroughDeviceArgs, VMDeviceUsbPassthroughDeviceResult, VMDeviceUsbPassthroughChoicesArgs,
    VMDeviceUsbPassthroughChoicesResult, VMDeviceUsbControllerChoicesArgs, VMDeviceUsbControllerChoicesResult,
    VMUSBDevice,
)
from middlewared.service import Service


class VMDeviceService(Service):

    class Config:
        namespace = 'vm.device'

    @api_method(VMDeviceUsbControllerChoicesArgs, VMDeviceUsbControllerChoicesResult, roles=['VM_DEVICE_READ'])
    async def usb_controller_choices(self):
        """
        Retrieve USB controller type choices
        """
        return {k: k for k in get_args(VMUSBDevice.model_fields['controller_type'].annotation)}

    @api_method(VMDeviceUsbPassthroughDeviceArgs, VMDeviceUsbPassthroughDeviceResult, roles=['VM_DEVICE_READ'])
    def usb_passthrough_device(self, port):
        """
        Retrieve details about the USB device currently plugged into `port`.
        """
        info = USBInventory.collect().by_port(port)
        return info.as_choice() if info else None

    @api_method(
        VMDeviceUsbPassthroughChoicesArgs, VMDeviceUsbPassthroughChoicesResult, roles=['VM_DEVICE_READ']
    )
    def usb_passthrough_choices(self):
        """
        Available choices for USB passthrough devices.
        """
        return get_all_usb_devices()
