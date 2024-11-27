import re

from xml.etree import ElementTree as etree

from middlewared.api import api_method
from middlewared.api.current import (
    VMDeviceUSBPassthroughDeviceArgs, VMDeviceUSBPassthroughDeviceResult, VMDeviceUSBPassthroughDeviceChoicesArgs,
    VMDeviceUSBPassthroughDeviceChoicesResult, VMDeviceUSBControllerChoicesArgs, VMDeviceUSBControllerChoicesResult,
)
from middlewared.service import CallError, private, Service
from middlewared.utils import run

from .devices.usb import USB_CONTROLLER_CHOICES
from .utils import get_virsh_command_args


RE_VALID_USB_DEVICE = re.compile(r'^usb_\d+_\d+(?:_\d)*$')


class VMDeviceService(Service):

    class Config:
        namespace = 'vm.device'

    @api_method(VMDeviceUSBControllerChoicesArgs, VMDeviceUSBControllerChoicesResult, roles=['VM_DEVICE_READ'])
    async def usb_controller_choices(self):
        """
        Retrieve USB controller type choices
        """
        return {k: k for k in USB_CONTROLLER_CHOICES}

    @private
    def retrieve_usb_device_information(self, xml_str):
        xml = etree.fromstring(xml_str.strip())
        capability = next((e for e in list(xml) if e.tag == 'capability'), None)
        if capability is None:
            return capability
        required_keys = set(self.get_capability_keys())
        capability_info = {}
        for element in filter(lambda e: e.tag in required_keys and e.text is not None, capability):
            capability_info[element.tag] = element.text
            if element.tag in ('product', 'vendor') and element.get('id'):
                capability_info[f'{element.tag}_id'] = element.get('id')

        return None if set(capability_info) != required_keys else capability_info

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

    @api_method(VMDeviceUSBPassthroughDeviceArgs, VMDeviceUSBPassthroughDeviceResult, roles=['VM_DEVICE_READ'])
    async def usb_passthrough_device(self, device):
        """
        Retrieve details about `device` USB device.
        """
        await self.middleware.call('vm.check_setup_libvirt')
        data = await self.get_basic_usb_passthrough_device_data()
        cp = await run(get_virsh_command_args() + ['nodedev-dumpxml', device], check=False)
        if cp.returncode:
            data['error'] = cp.stderr.decode()
            return data

        capability_info = await self.middleware.call(
            'vm.device.retrieve_usb_device_information', cp.stdout.decode()
        )
        if not capability_info:
            data['error'] = 'Unable to determine capabilities of USB device'
        else:
            data['capability'] = capability_info

        return {
            **data,
            'available': not data['error'],
        }

    @private
    async def get_basic_usb_passthrough_device_data(self):
        return {
            'capability': self.get_capability_keys(),
            'available': False,
            'error': None,
        }

    @api_method(
        VMDeviceUSBPassthroughDeviceChoicesArgs, VMDeviceUSBPassthroughDeviceChoicesResult, roles=['VM_DEVICE_READ']
    )
    async def usb_passthrough_choices(self):
        """
        Available choices for USB passthrough devices.
        """
        await self.middleware.call('vm.check_setup_libvirt')

        cp = await run(get_virsh_command_args() + ['nodedev-list', 'usb_device'], check=False)
        if cp.returncode:
            raise CallError(f'Unable to retrieve USB devices: {cp.stderr.decode()}')

        devices = [k for k in map(str.strip, cp.stdout.decode().split('\n')) if RE_VALID_USB_DEVICE.findall(k)]
        mapping = {}
        for device in devices:
            details = await self.usb_passthrough_device(device)
            if details['error']:
                continue
            mapping[device] = details

        return mapping

    @private
    async def get_usb_port_from_usb_details(self, usb_data):
        if any(not usb_data.get(k) for k in ('product_id', 'vendor_id')):
            raise CallError('Product / Vendor ID must be specified for USBs')

        for device, device_details in (await self.usb_passthrough_choices()).items():
            capability = device_details['capability']
            if all(usb_data[k] == capability[k] for k in ('product_id', 'vendor_id')):
                return device
