from truenas_pylibvirt.utils.pci import (
    get_pci_device_default_data, get_all_pci_devices_details, get_single_pci_device_details, iommu_enabled,
)

from middlewared.api import api_method
from middlewared.api.current import (
    VMDeviceIommuEnabledArgs, VMDeviceIommuEnabledResult, VMDevicePassthroughDeviceArgs,
    VMDevicePassthroughDeviceResult, VMDevicePassthroughDeviceChoicesArgs, VMDevicePassthroughDeviceChoicesResult,
)
from middlewared.service import Service


class VMDeviceService(Service):

    class Config:
        namespace = 'vm.device'

    @api_method(VMDeviceIommuEnabledArgs, VMDeviceIommuEnabledResult, roles=['VM_DEVICE_READ'])
    def iommu_enabled(self):
        """Returns "true" if iommu is enabled, "false" otherwise"""
        return iommu_enabled()

    @api_method(VMDevicePassthroughDeviceArgs, VMDevicePassthroughDeviceResult, roles=['VM_DEVICE_READ'])
    def passthrough_device(self, device):
        """Retrieve details about `device` PCI device"""
        if device_details := get_single_pci_device_details(device):
            return device_details[device]
        else:
            return {
                **get_pci_device_default_data(),
                'error': 'Device not found',
            }

    @api_method(VMDevicePassthroughDeviceChoicesArgs, VMDevicePassthroughDeviceChoicesResult, roles=['VM_DEVICE_READ'])
    def passthrough_device_choices(self):
        """Available choices for PCI passthru devices"""
        return get_all_pci_devices_details()
