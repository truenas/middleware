import collections
import os
import pathlib
import re

from pyudev import Context

from middlewared.schema import accepts, Bool, Dict, Int, List, Ref, returns, Str
from middlewared.service import private, Service, ValidationErrors
from middlewared.utils.gpu import get_gpus, SENSITIVE_PCI_DEVICE_TYPES

from .utils import convert_pci_id_to_vm_pci_slot, get_pci_device_class


RE_DEVICE_NAME = re.compile(r'(\w+):(\w+):(\w+).(\w+)')
RE_DEVICE_PATH = re.compile(r'pci_(\w+)_(\w+)_(\w+)_(\w+)')


class VMDeviceService(Service):

    class Config:
        namespace = 'vm.device'

    @accepts(roles=['VM_DEVICE_READ'])
    @returns(Bool())
    def iommu_enabled(self):
        """Returns "true" if iommu is enabled, "false" otherwise"""
        return os.path.exists('/sys/kernel/iommu_groups')

    @private
    def get_iommu_groups_info(self):
        addresses = collections.defaultdict(list)
        final = dict()
        try:
            for i in pathlib.Path('/sys/kernel/iommu_groups').glob('*/devices/*'):
                if not i.is_dir() or not i.parent.parent.name.isdigit() or not RE_DEVICE_NAME.fullmatch(i.name):
                    continue

                iommu_group = int(i.parent.parent.name)
                dbs, func = i.name.split('.')
                dom, bus, slot = dbs.split(':')
                addresses[iommu_group].append({
                    'domain': f'0x{dom}',
                    'bus': f'0x{bus}',
                    'slot': f'0x{slot}',
                    'function': f'0x{func}',
                })
                final[i.name] = {'number': iommu_group, 'addresses': addresses[iommu_group]}
        except FileNotFoundError:
            pass

        return final

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
            'iommu_group': {},
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
        iommu_info = self.get_iommu_groups_info()
        for i in Context().list_devices(subsystem='pci'):
            key = f"pci_{i.sys_name.replace(':', '_').replace('.', '_')}"
            result[key] = self.get_pci_device_details(i, iommu_info)
        return result

    @private
    def get_single_pci_device_details(self, pcidev):
        result = dict()
        iommu_info = self.get_iommu_groups_info()
        for i in filter(lambda x: x.sys_name == pcidev, Context().list_devices(subsystem='pci')):
            key = f"pci_{i.sys_name.replace(':', '_').replace('.', '_')}"
            result[key] = self.get_pci_device_details(i, iommu_info)
        return result

    @accepts(Str('device'), roles=['VM_DEVICE_READ'])
    @returns(Dict(
        'passthrough_device',
        Dict(
            'capability',
            Str('class', null=True, required=True),
            Str('domain', null=True, required=True),
            Str('bus', null=True, required=True),
            Str('slot', null=True, required=True),
            Str('function', null=True, required=True),
            Str('product', null=True, required=True),
            Str('vendor', null=True, required=True),
            required=True,
        ),
        Str('controller_type', null=True, required=True),
        Dict(
            'iommu_group',
            Int('number', required=True),
            List('addresses', items=[Dict(
                'address',
                Str('domain', required=True),
                Str('bus', required=True),
                Str('slot', required=True),
                Str('function', required=True),
            )]),
            required=True,
        ),
        Bool('available', required=True),
        List('drivers', items=[Str('driver', required=False)], required=True),
        Str('error', null=True, required=True),
        Str('device_path', null=True, required=True),
        Bool('reset_mechanism_defined', required=True),
        Str('description', empty=True, required=True),
        register=True,
    ))
    def passthrough_device(self, device):
        """Retrieve details about `device` PCI device"""
        base_default = self.get_pci_device_default_data()
        if not self.middleware.call_sync('vm.check_setup_libvirt'):
            return {
                **base_default,
                'error': 'Virtualization is not setup on this system',
            }

        if device_details := self.get_single_pci_device_details(RE_DEVICE_PATH.sub(r'\1:\2:\3.\4', device)):
            return device_details[device]
        else:
            return {
                **base_default,
                'error': 'Device not found',
            }

    @accepts(roles=['VM_DEVICE_READ'])
    @returns(List(items=[Ref('passthrough_device')], register=True))
    def passthrough_device_choices(self):
        """Available choices for PCI passthru devices"""
        return self.get_all_pci_devices_details()

    @accepts()
    @returns(Ref('passthrough_device_choices'))
    def pptdev_choices(self):
        """Available choices for PCI passthru device"""
        return self.get_all_pci_devices_details()

    @accepts(Str('gpu_pci_id', empty=False))
    @returns(List(items=[Str('pci_ids')]))
    def get_pci_ids_for_gpu_isolation(self, gpu_pci_id):
        """
        Get PCI IDs of devices which are required to be isolated for `gpu_pci_id` GPU isolation.

        Basically when a GPU passthrough is desired for a VM, we need to isolate all the devices which are in the same
        IOMMU group as the GPU. This is required because if we don't do this, the VM will not be able to start because
        the devices in the same IOMMU group as the GPU will be in use by the host and will not be available for the VM
        to use.

        This endpoints retrieves all the PCI devices which are in the same IOMMU group as the GPU and returns their PCI
        IDs so UI can use those and create PCI devices for them and isolate them.
        """
        gpu = next((gpu for gpu in get_gpus() if gpu['addr']['pci_slot'] == gpu_pci_id), None)
        verrors = ValidationErrors()
        if not gpu:
            verrors.add('gpu_pci_id', f'GPU with {gpu_pci_id!r} PCI ID not found')

        verrors.check()

        iommu_groups = self.get_iommu_groups_info()
        iommu_groups_mapping_with_group_no = collections.defaultdict(set)
        for pci_slot, pci_details in iommu_groups.items():
            iommu_groups_mapping_with_group_no[pci_details['number']].add(convert_pci_id_to_vm_pci_slot(pci_slot))

        pci_ids = set()
        for device in gpu['devices']:
            if not (device_info := iommu_groups.get(device['pci_slot'])):
                continue

            pci_ids.update(iommu_groups_mapping_with_group_no[device_info['number']])

        return list(pci_ids)
