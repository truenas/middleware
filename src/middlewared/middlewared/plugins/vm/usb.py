import re

from truenas_pylibvirt.utils.usb import get_all_usb_devices, find_usb_device_by_libvirt_name

from middlewared.api import api_method
from middlewared.api.current import (
    VMDeviceUsbPassthroughDeviceArgs, VMDeviceUsbPassthroughDeviceResult, VMDeviceUsbPassthroughChoicesArgs,
    VMDeviceUsbPassthroughChoicesResult, VMDeviceUsbControllerChoicesArgs, VMDeviceUsbControllerChoicesResult,
)
from middlewared.service import CallError, private, Service
from middlewared.utils.libvirt.usb import USB_CONTROLLER_CHOICES


RE_VALID_USB_DEVICE = re.compile(r'^usb_\d+_\d+(?:_\d)*$')


class VMDeviceService(Service):

    class Config:
        namespace = 'vm.device'

    @api_method(VMDeviceUsbControllerChoicesArgs, VMDeviceUsbControllerChoicesResult, roles=['VM_DEVICE_READ'])
    async def usb_controller_choices(self):
        """
        Retrieve USB controller type choices
        """
        return {k: k for k in USB_CONTROLLER_CHOICES}

    @private
    def get_capability_keys(self):
        return {
            'product': None,
            'vendor': None,
            'product_id': None,
            'vendor_id': None,
            'bus': None,
            'device': None,
        }

    @api_method(VMDeviceUsbPassthroughDeviceArgs, VMDeviceUsbPassthroughDeviceResult, roles=['VM_DEVICE_READ'])
    async def usb_passthrough_device(self, device):
        """
        Retrieve details about `device` USB device.
        """
        return find_usb_device_by_libvirt_name(device)

    @private
    async def get_basic_usb_passthrough_device_data(self):
        # TODO: Remove this too when we remove middleware usb device implementation
        return {
            'capability': self.get_capability_keys(),
            'available': False,
            'error': None,
        }

    @api_method(
        VMDeviceUsbPassthroughChoicesArgs, VMDeviceUsbPassthroughChoicesResult, roles=['VM_DEVICE_READ']
    )
    async def usb_passthrough_choices(self):
        """
        Available choices for USB passthrough devices.
        """
        return get_all_usb_devices()

    @private
    async def get_usb_port_from_usb_details(self, usb_data):
        if any(not usb_data.get(k) for k in ('product_id', 'vendor_id')):
            raise CallError('Product / Vendor ID must be specified for USBs')

        for device, device_details in (await self.usb_passthrough_choices()).items():
            capability = device_details['capability']
            if all(usb_data[k] == capability[k] for k in ('product_id', 'vendor_id')):
                return device
