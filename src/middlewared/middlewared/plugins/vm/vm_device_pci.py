from __future__ import annotations

from truenas_pylibvirt.utils.pci import (
    get_all_pci_devices_details,
    get_pci_device_default_data,
    get_single_pci_device_details,
)
from truenas_pylibvirt.utils.pci import (
    iommu_enabled as _iommu_enabled,
)

from middlewared.api.current import VMDevicePassthroughDevice, VMDevicePassthroughInfo


def iommu_enabled() -> bool:
    return _iommu_enabled()


def passthrough_device(device: str) -> VMDevicePassthroughDevice:
    if device_details := get_single_pci_device_details(device):
        data = device_details[device]
    else:
        data = {**get_pci_device_default_data(), 'error': 'Device not found'}
    return VMDevicePassthroughDevice.model_validate(data)


def passthrough_device_choices() -> VMDevicePassthroughInfo:
    return VMDevicePassthroughInfo.model_validate(get_all_pci_devices_details())
