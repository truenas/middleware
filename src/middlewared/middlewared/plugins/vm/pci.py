import os
import re

from pyudev import Context

from middlewared.api import api_method
from middlewared.api.current import (
    VMDeviceIommuEnabledArgs, VMDeviceIommuEnabledResult, VMDevicePassthroughDeviceArgs,
    VMDevicePassthroughDeviceResult, VMDevicePassthroughDeviceChoicesArgs, VMDevicePassthroughDeviceChoicesResult,
    VMDevicePptdevChoicesArgs, VMDevicePptdevChoicesResult,
)
from middlewared.service import private, Service
from middlewared.utils.iommu import get_iommu_groups_info
from middlewared.utils.pci import get_pci_device_class, SENSITIVE_PCI_DEVICE_TYPES


RE_DEVICE_PATH = re.compile(r'pci_(\w+)_(\w+)_(\w+)_(\w+)')


class VMDeviceService(Service):

    class Config:
        namespace = 'vm.device'

    @api_method(VMDeviceIommuEnabledArgs, VMDeviceIommuEnabledResult, roles=['VM_DEVICE_READ'])
    def iommu_enabled(self):
        """Returns "true" if iommu is enabled, "false" otherwise"""
        return os.path.exists('/sys/kernel/iommu_groups')

    @private
    def get_pci_device_default_data(self):
        return {
            'capability': {
                'class': None,
                'domain': None,
                'bus': None,
                'slot': None,
                'function': None,
                'product': 'Not Available',
                'vendor': 'Not Available',
            },
            'controller_type': None,
            'critical': False,
            'iommu_group': None,
            'available': False,
            'drivers': [],
            'error': None,
            'device_path': None,
            'reset_mechanism_defined': False,
            'description': '',
        }

    @private
    def get_pci_device_details(self, obj, iommu_info):
        data = self.get_pci_device_default_data()
        if not (igi := iommu_info.get(obj.sys_name)):
            data['error'] = 'Unable to determine iommu group'

        dbs, func = obj.sys_name.split('.')
        dom, bus, slot = dbs.split(':')
        device_path = os.path.join('/sys/bus/pci/devices', obj.sys_name)
        cap_class = f'{(obj.attributes.get("class") or b"").decode()}' or get_pci_device_class(device_path)
        controller_type = obj.properties.get('ID_PCI_SUBCLASS_FROM_DATABASE') or SENSITIVE_PCI_DEVICE_TYPES.get(
            cap_class[:6]
        )

        drivers = []
        if driver := obj.properties.get('DRIVER'):
            drivers.append(driver)

        data['capability']['class'] = cap_class or None
        data['capability']['domain'] = f'{int(dom, base=16)}'
        data['capability']['bus'] = f'{int(bus, base=16)}'
        data['capability']['slot'] = f'{int(slot, base=16)}'
        data['capability']['function'] = f'{int(func, base=16)}'
        data['capability']['product'] = obj.properties.get('ID_MODEL_FROM_DATABASE', 'Not Available')
        data['capability']['vendor'] = obj.properties.get('ID_VENDOR_FROM_DATABASE', 'Not Available')
        data['controller_type'] = controller_type
        data['critical'] = bool(not cap_class or SENSITIVE_PCI_DEVICE_TYPES.get(cap_class[:6]))
        data['iommu_group'] = igi
        data['available'] = all(i == 'vfio-pci' for i in drivers) and not data['critical']
        data['drivers'] = drivers
        data['device_path'] = os.path.join('/sys/bus/pci/devices', obj.sys_name)
        data['reset_mechanism_defined'] = os.path.exists(os.path.join(data['device_path'], 'reset'))

        prefix = obj.sys_name + (f' {controller_type!r}' if controller_type else '')
        vendor = data['capability']['vendor'].strip()
        suffix = data['capability']['product'].strip()
        if vendor and suffix:
            data['description'] = f'{prefix}: {suffix} by {vendor!r}'
        else:
            data['description'] = prefix

        return data

    @private
    def get_all_pci_devices_details(self):
        result = dict()
        iommu_info = get_iommu_groups_info()
        for i in Context().list_devices(subsystem='pci'):
            key = f"pci_{i.sys_name.replace(':', '_').replace('.', '_')}"
            result[key] = self.get_pci_device_details(i, iommu_info)
        return result

    @private
    def get_single_pci_device_details(self, pcidev):
        result = dict()
        iommu_info = get_iommu_groups_info()
        for i in filter(lambda x: x.sys_name == pcidev, Context().list_devices(subsystem='pci')):
            key = f"pci_{i.sys_name.replace(':', '_').replace('.', '_')}"
            result[key] = self.get_pci_device_details(i, iommu_info)
        return result

    @api_method(VMDevicePassthroughDeviceArgs, VMDevicePassthroughDeviceResult, roles=['VM_DEVICE_READ'])
    def passthrough_device(self, device):
        """Retrieve details about `device` PCI device"""
        self.middleware.call_sync('vm.check_setup_libvirt')
        if device_details := self.get_single_pci_device_details(RE_DEVICE_PATH.sub(r'\1:\2:\3.\4', device)):
            return device_details[device]
        else:
            return {
                **self.get_pci_device_default_data(),
                'error': 'Device not found',
            }

    @api_method(VMDevicePassthroughDeviceChoicesArgs, VMDevicePassthroughDeviceChoicesResult, roles=['VM_DEVICE_READ'])
    def passthrough_device_choices(self):
        """Available choices for PCI passthru devices"""
        return self.get_all_pci_devices_details()

    @api_method(VMDevicePptdevChoicesArgs, VMDevicePptdevChoicesResult, roles=['VM_DEVICE_READ'])
    def pptdev_choices(self):
        """Available choices for PCI passthru device"""
        return self.get_all_pci_devices_details()
