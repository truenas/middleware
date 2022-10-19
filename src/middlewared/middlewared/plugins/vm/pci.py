import os
import re

from xml.etree import ElementTree as etree

from middlewared.schema import accepts, Bool, Dict, List, Ref, returns, Str
from middlewared.service import CallError, private, Service
from middlewared.utils import run

from .utils import get_virsh_command_args


RE_DEVICE_PATH = re.compile(r'pci_(\w+)_(\w+)_(\w+)_(\w+)')
RE_IOMMU_ENABLED = re.compile(r'QEMU.*if IOMMU is enabled.*:\s*PASS.*')
RE_PCI_CONTROLLER_TYPE = re.compile(r'^[\w:.]+\s+([\w\s]+)\s+\[')
RE_PCI_NAME = re.compile(r'^([\w:.]+)\s+')


class VMDeviceService(Service):

    PCI_DEVICES = None
    SENSITIVE_PCI_DEVICE_TYPES = (
        'Host bridge',
        'Bridge',
        'RAM memory',
        'SMBus',
    )

    class Config:
        namespace = 'vm.device'

    @accepts()
    @returns(Bool())
    async def iommu_enabled(self):
        """
        Returns "true" if iommu is enabled, "false" otherwise
        """
        cp = await run(['virt-host-validate'], check=False)
        # We still check for stdout because if some check in it fails, the command will have a non zero exit code
        return bool(RE_IOMMU_ENABLED.findall((cp.stdout or b'').decode()))

    @private
    def retrieve_node_information(self, xml):
        info = {'capability': {}, 'iommu_group': {'number': None, 'addresses': []}}
        capability = next((e for e in list(xml) if e.tag == 'capability' and e.get('type') == 'pci'), None)
        if capability is None:
            return info

        for child in list(capability):
            if child.tag == 'iommuGroup':
                if not child.get('number'):
                    continue
                info['iommu_group']['number'] = int(child.get('number'))
                for address in list(child):
                    info['iommu_group']['addresses'].append({
                        'domain': address.get('domain'),
                        'bus': address.get('bus'),
                        'slot': address.get('slot'),
                        'function': address.get('function'),
                    })
            elif not list(child) and child.text:
                info['capability'][child.tag] = child.text

        return info

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
        register=True,
    ))
    async def passthrough_device(self, device):
        """
        Retrieve details about `device` PCI device.
        """
        await self.middleware.call('vm.check_setup_libvirt')
        pci_id = RE_DEVICE_PATH.sub(r'\1:\2:\3.\4', device)
        controller_type = (await self.get_pci_devices()).get(pci_id)

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
            'controller_type': controller_type,
            'critical': controller_type in self.SENSITIVE_PCI_DEVICE_TYPES,
            'iommu_group': {},
            'available': False,
            'drivers': [],
            'error': None,
            'device_path': os.path.join('/sys/bus/pci/devices', pci_id),
            'reset_mechanism_defined': False,
        }
        cp = await run(get_virsh_command_args() + ['nodedev-dumpxml', device], check=False)
        if cp.returncode:
            data['error'] = cp.stderr.decode()
            return data

        xml = etree.fromstring(cp.stdout.decode().strip())
        driver = next((e for e in list(xml) if e.tag == 'driver'), None)
        drivers = [e.text for e in list(driver)] if driver is not None else []

        node_info = await self.middleware.call('vm.device.retrieve_node_information', xml)
        error_str = ''

        if node_info['iommu_group'].get('number') is None:
            error_str += 'Unable to determine iommu group\n'
        if any(not node_info['capability'].get(k) for k in ('domain', 'bus', 'slot', 'function')):
            error_str += 'Unable to determine PCI device address\n'

        return {
            **node_info,
            **{k: data[k] for k in ('controller_type', 'critical', 'device_path')},
            'drivers': drivers,
            'available': not error_str and all(d == 'vfio-pci' for d in drivers) and not data['critical'],
            'error': f'Following errors were found with the device:\n{error_str}' if error_str else None,
            'reset_mechanism_defined': os.path.exists(os.path.join(data['device_path'], 'reset')),
        }

    @accepts()
    @returns(List(items=[Ref('passthrough_device')], register=True))
    async def passthrough_device_choices(self):
        """
        Available choices for PCI passthru devices.
        """
        # We need to check if libvirtd is running because it's possible that no vm has been configured yet
        # which will result in libvirtd not running and trying to list pci devices for passthrough fail.
        await self.middleware.call('vm.check_setup_libvirt')

        cp = await run(get_virsh_command_args() + ['nodedev-list', 'pci'], check=False)
        if cp.returncode:
            raise CallError(f'Unable to retrieve PCI devices: {cp.stderr.decode()}')
        pci_devices = [k.strip() for k in cp.stdout.decode().split('\n') if k.strip()]
        mapping = {}
        for pci in pci_devices:
            details = await self.passthrough_device(pci)
            if details['error']:
                continue
            mapping[pci] = details

        return mapping

    @private
    async def get_pci_devices(self):
        if self.PCI_DEVICES is None:
            self.PCI_DEVICES = {}
            cp = await run(['lspci', '-nnD'], check=False, encoding='utf8', errors='ignore')
            if not cp.returncode:
                for pci_device_str in cp.stdout.splitlines():
                    pci_id = RE_PCI_NAME.findall(pci_device_str)
                    controller_type = RE_PCI_CONTROLLER_TYPE.findall(pci_device_str)
                    if pci_id:
                        self.PCI_DEVICES[pci_id[0]] = controller_type[0] if controller_type else None

        return self.PCI_DEVICES

    @accepts()
    @returns(Ref('passthrough_device_choices'))
    async def pptdev_choices(self):
        """
        Available choices for PCI passthru device.
        """
        return await self.passthrough_device_choices()
