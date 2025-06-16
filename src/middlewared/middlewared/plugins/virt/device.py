from dataclasses import asdict

from middlewared.api import api_method
from middlewared.api.current import (
    VirtDeviceUsbChoicesArgs, VirtDeviceUsbChoicesResult,
    VirtDeviceGpuChoicesArgs, VirtDeviceGpuChoicesResult,
    VirtDeviceDiskChoicesArgs, VirtDeviceDiskChoicesResult,
    VirtDeviceNicChoicesArgs, VirtDeviceNicChoicesResult,
    VirtDevicePciChoicesArgs, VirtDevicePciChoicesResult,
)
from middlewared.service import CallError, private, Service
from middlewared.utils.functools_ import cache
from middlewared.utils.pci import get_all_pci_devices_details
from middlewared.utils.usb import list_usb_devices

from .utils import PciEntry


class VirtDeviceService(Service):

    class Config:
        namespace = 'virt.device'
        cli_namespace = 'virt.device'

    @api_method(VirtDeviceUsbChoicesArgs, VirtDeviceUsbChoicesResult, roles=['VIRT_INSTANCE_READ'])
    def usb_choices(self):
        """
        Provide choices for USB devices.
        """
        return list_usb_devices()

    @api_method(VirtDeviceGpuChoicesArgs, VirtDeviceGpuChoicesResult, roles=['VIRT_INSTANCE_READ'])
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

    @private
    async def disk_choices_internal(self, include_in_use=False):
        """
        This allows optionally including in-use choices because update payloads with
        /dev/zvol paths are validated against it in instance_device.py. If our validation
        changes at some time in the future we can consolidate this method with the public
        disk_choices method.
        """
        if include_in_use:
            incus_vol_filter = []
            zvol_filter = ['OR', [
                ['attachment', '=', None],
                ['attachment.method', '=', 'virt.instance.query']
            ]]
        else:
            incus_vol_filter = [["used_by", "=", []]]
            zvol_filter = ['attachment', '=', None]

        out = {}
        for incus_vol in await self.middleware.call('virt.volume.query', incus_vol_filter):
            out[incus_vol['id']] = incus_vol['id']

        for zvol in await self.middleware.call(
            'zfs.dataset.unlocked_zvols_fast', [
                zvol_filter, ['ro', '=', False],
            ],
            {}, ['ATTACHMENT', 'RO']
        ):
            out[zvol['path']] = zvol['name']

        return out

    @api_method(VirtDeviceDiskChoicesArgs, VirtDeviceDiskChoicesResult, roles=['VIRT_INSTANCE_READ'])
    async def disk_choices(self):
        """
        Returns disk choices available for device type "DISK" for virtual machines. This includes
        both available virt volumes and zvol choices. Disk choices for containers depend on the
        mounted file tree (paths).
        """
        return await self.disk_choices_internal()

    @api_method(VirtDeviceNicChoicesArgs, VirtDeviceNicChoicesResult, roles=['VIRT_INSTANCE_READ'])
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

    @api_method(VirtDevicePciChoicesArgs, VirtDevicePciChoicesResult, roles=['VIRT_INSTANCE_READ'])
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
