import collections
import os
import pathlib
import re

from pyudev import Context

from middlewared.schema import accepts, Bool, Dict, List, Ref, returns, Str
from middlewared.service import private, Service
from middlewared.utils.gpu import SENSITIVE_PCI_DEVICE_TYPES

RE_DEVICE_PATH = re.compile(r'pci_(\w+)_(\w+)_(\w+)_(\w+)')


class VMDeviceService(Service):

    class Config:
        namespace = 'vm.device'

    @accepts()
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
                if not i.is_dir() or not i.parent.parent.name.isdigit():
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
    def get_pci_device_details(self, obj, iommu_info):
        data = {
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
        if not (igi := iommu_info.get(obj.sys_name)):
            data['error'] = 'Unable to determine iommu group'

        dbs, func = obj.sys_name.split('.')
        dom, bus, slot = dbs.split(':')
        cap_class = f'{(obj.attributes.get("class") or b"").decode() or None}'
        ctrl_type = obj.properties.get('ID_PCI_SUBCLASS_FROM_DATABASE')
        drivers = []
        if (driver := obj.properties.get('DRIVER')):
            drivers.append(driver)

        data['capability']['class'] = cap_class
        data['capability']['domain'] = f'{int(dom, base=16)}'
        data['capability']['bus'] = f'{int(bus, base=16)}'
        data['capability']['slot'] = f'{int(slot, base=16)}'
        data['capability']['function'] = f'{int(func, base=16)}'
        data['capability']['product'] = obj.properties.get('ID_MODEL_FROM_DATABASE', 'Not Available')
        data['capability']['vendor'] = obj.properties.get('ID_VENDOR_FROM_DATABASE', 'Not Available')
        data['controller_type'] = ctrl_type
        data['critical'] = any(not ctrl_type or i.lower() in ctrl_type.lower() for i in SENSITIVE_PCI_DEVICE_TYPES)
        data['iommu_group'] = igi
        data['available'] = all(i == 'vfio-pci' for i in drivers) and not data['critical']
        data['drivers'] = drivers
        data['device_path'] = os.path.join('/sys/bus/pci/devices', obj.sys_name)
        data['reset_mechanism_defined'] = os.path.exists(os.path.join(data['device_path'], 'reset'))

        prefix = obj.sys_name + (f' {ctrl_type!r}' if ctrl_type else '')
        vendor = (data['capability']['vendor'] or '').strip()
        suffix = (data['capability']['product'] or '').strip()
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

    @accepts(Str('device'))
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
        Dict('iommu_group', additional_attrs=True, required=True),
        List('drivers', required=True),
        Bool('available', required=True),
        Bool('reset_mechanism_defined', required=True),
        Str('error', null=True, required=True),
        Str('device_path', null=True, required=True),
        Str('description', empty=True, required=True),
        register=True,
    ))
    def passthrough_device(self, device):
        """Retrieve details about `device` PCI device"""
        self.middleware.call_sync('vm.check_setup_libvirt')
        return self.get_single_pci_device_details(RE_DEVICE_PATH.sub(r'\1:\2:\3.\4', device))

    @accepts()
    @returns(List(items=[Ref('passthrough_device')], register=True))
    def passthrough_device_choices(self):
        """Available choices for PCI passthru devices"""
        return self.get_all_pci_devices_details()

    @accepts()
    @returns(Ref('passthrough_device_choices'))
    def pptdev_choices(self):
        """Available choices for PCI passthru device"""
        return self.get_all_pci_devices_details()
