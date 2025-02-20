from dataclasses import asdict

import usb.core

from middlewared.api import api_method
from middlewared.api.current import (
    VirtDeviceUSBChoicesArgs, VirtDeviceUSBChoicesResult,
    VirtDeviceGPUChoicesArgs, VirtDeviceGPUChoicesResult,
    VirtDeviceDiskChoicesArgs, VirtDeviceDiskChoicesResult,
    VirtDeviceNICChoicesArgs, VirtDeviceNICChoicesResult,
    VirtDevicePCIChoicesArgs, VirtDevicePCIChoicesResult,
)
from middlewared.service import CallError, private, Service
from middlewared.utils.functools_ import cache
from middlewared.utils.pci import get_all_pci_devices_details

from .utils import PciEntry


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
    async def gpu_choices(self, gpu_type):
        """
        Provide choices for GPU devices.
        """
        choices = {}

        if gpu_type != 'PHYSICAL':
            raise CallError('Only PHYSICAL type is supported for now.')

        for i in await self.middleware.call('device.get_gpus'):
            if not i['available_to_host'] or i['uses_system_critical_devices']:
                continue
            choices[i['addr']['pci_slot']] = {
                'bus': i['addr']['bus'],
                'slot': i['addr']['slot'],
                'description': i['description'],
                'vendor': i['vendor'],
                'pci': i['addr']['pci_slot'],
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

    @api_method(VirtDeviceNICChoicesArgs, VirtDeviceNICChoicesResult, roles=['VIRT_INSTANCE_READ'])
    async def nic_choices(self, nic_type):
        """
        Returns choices for NIC device.
        """
        choices = {}
        match nic_type:
            case 'BRIDGED':
                choices = {i['id']: i['name'] for i in await self.middleware.call(
                    'interface.query', [['type', '=', 'BRIDGE']]
                )}
            case 'MACVLAN':
                choices = {i['id']: i['name'] for i in await self.middleware.call(
                    'interface.query',
                )}
        return choices

    @api_method(VirtDevicePCIChoicesArgs, VirtDevicePCIChoicesResult, roles=['VIRT_INSTANCE_READ'])
    def pci_choices(self):
        """
        Returns choices for PCI devices valid for VM virt instances.
        """
        pci_choices = {}
        for i in self.get_pci_devices_choices_cache():
            pci_details = asdict(i)
            if pci_details['critical'] is False and not pci_details['error']:
                pci_choices[pci_details['pci_addr']] = pci_details

        return pci_choices

    @private
    @cache
    def get_pci_devices_choices_cache(self) -> tuple[PciEntry]:
        result = list()
        for pci_addr, pci_details in get_all_pci_devices_details().items():
            result.append(PciEntry(pci_addr=pci_addr, **pci_details))

        return tuple(result)
