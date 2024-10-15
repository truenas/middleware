import usb.core

from middlewared.service import CallError, Service

from middlewared.api import api_method
from middlewared.api.current import (
    VirtDeviceUSBChoicesArgs, VirtDeviceUSBChoicesResult,
    VirtDeviceGPUChoicesArgs, VirtDeviceGPUChoicesResult,
    VirtDeviceDiskChoicesArgs, VirtDeviceDiskChoicesResult,
)


class VirtDeviceService(Service):

    class Config:
        namespace = 'virt.device'
        cli_namespace = 'virt.device'

    @api_method(VirtDeviceUSBChoicesArgs, VirtDeviceUSBChoicesResult, roles=['VIRT_INSTANCE_READ'])
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

    @api_method(VirtDeviceGPUChoicesArgs, VirtDeviceGPUChoicesResult, roles=['VIRT_INSTANCE_READ'])
    async def gpu_choices(self, instance_type, gpu_type):
        """
        Provide choices for GPU devices.
        """
        choices = {}

        if gpu_type != 'PHYSICAL':
            raise CallError('Only PHYSICAL type is supported for now.')

        if instance_type != 'CONTAINER':
            raise CallError('Only CONTAINER supported for now.')

        for i in await self.middleware.call('device.get_gpus'):
            if not i['available_to_host'] or i['uses_system_critical_devices']:
                continue
            choices[i['addr']['pci_slot']] = {
                'bus': i['addr']['bus'],
                'slot': i['addr']['slot'],
                'description': i['description'],
                'vendor': i['vendor'],
            }
        return choices

    @api_method(VirtDeviceDiskChoicesArgs, VirtDeviceDiskChoicesResult, roles=['VIRT_INSTANCE_READ'])
    async def disk_choices(self):
        """
        Returns disk (zvol) choices for device type "DISK".
        """
        out = {}
        zvols = await self.middleware.call(
            'zfs.dataset.unlocked_zvols_fast', [
                ['OR', [['attachment', '=', None], ['attachment.method', '=', 'virt.instance.query']]],
                ['ro', '=', False],
            ],
            {}, ['ATTACHMENT', 'RO']
        )

        for zvol in zvols:
            out[zvol['path']] = zvol['name']

        return out
