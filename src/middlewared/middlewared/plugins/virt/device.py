import usb.core

from middlewared.service import CallError, Service

from middlewared.api import api_method
from middlewared.api.current import (
    VirtDeviceUSBChoicesArgs, VirtDeviceUSBChoicesResult,
    VirtDeviceGPUChoicesArgs, VirtDeviceGPUChoicesResult,
)
from middlewared.utils.gpu import get_gpus


class VirtDeviceService(Service):

    class Config:
        namespace = 'virt.device'
        cli_namespace = 'virt.device'

    @api_method(VirtDeviceUSBChoicesArgs, VirtDeviceUSBChoicesResult, roles=['VIRT_INSTANCES_READ'])
    def usb_choices(self):
        """
        Provide choices for USB devices.
        """
        choices = {}
        for i in usb.core.find(find_all=True):
            name = f'usb_{i.bus}_{i.address}'
            choices[name] = {
                'vendor_id': format(i.idVendor, '04x'),
                'product_id': format(i.idProduct, '04x'),
                'bus': i.bus,
                'dev': i.address,
                'product': i.product,
                'manufacturer': i.manufacturer,
            }
        return choices

    @api_method(VirtDeviceGPUChoicesArgs, VirtDeviceGPUChoicesResult, roles=['VIRT_INSTANCES_READ'])
    def gpu_choices(self, instance_type, gpu_type):
        """
        Provide choices for GPU devices.
        """
        choices = {}

        if gpu_type != 'PHYSICAL':
            raise CallError('Only PHYSICAL type is supported for now.')

        if instance_type != 'CONTAINER':
            raise CallError('Only CONTAINER supported for now.')

        for i in get_gpus():
            choices[i['addr']['pci_slot']] = {
                'bus': int(i['addr']['bus']),
                'slot': int(i['addr']['slot']),
                'description': i['description'],
                'vendor': i['vendor'],
            }
        return choices
