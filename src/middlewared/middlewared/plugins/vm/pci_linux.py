import re

from lxml import etree

from middlewared.service import CallError, private, Service
from middlewared.utils import run

from .pci_base import PCIInfoBase
from .utils import get_virsh_command_args


RE_IOMMU_ENABLED = re.compile(r'QEMU.*if IOMMU is enabled.*:\s*PASS.*')


class VMDeviceService(Service, PCIInfoBase):

    class Config:
        namespace = 'vm.device'

    async def iommu_enabled(self):
        cp = await run(['virt-host-validate'], check=False)
        # We still check for stdout because if some check in it fails, the command will have a non zero exit code
        return bool(RE_IOMMU_ENABLED.findall((cp.stdout or b'').decode()))

    @private
    def retrieve_node_information(self, xml):
        info = {'capability': {}, 'iommu_group': {'number': None, 'addresses': []}}
        capability = next((e for e in xml.getchildren() if e.tag == 'capability' and e.get('type') == 'pci'), None)
        if capability is None:
            return info

        for child in capability.getchildren():
            if child.tag == 'iommuGroup':
                if not child.get('number'):
                    continue
                info['iommu_group']['number'] = int(child.get('number'))
                for address in child.getchildren():
                    info['iommu_group']['addresses'].append({
                        'domain': address.get('domain'),
                        'bus': address.get('bus'),
                        'slot': address.get('slot'),
                        'function': address.get('function'),
                    })
            elif not child.getchildren() and child.text:
                info['capability'][child.tag] = child.text

        return info

    async def passthrough_device(self, device):
        await self.middleware.call('vm.check_setup_libvirt')
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
            'iommu_group': {},
            'available': False,
            'drivers': [],
            'error': None,
        }
        cp = await run(get_virsh_command_args() + ['nodedev-dumpxml', device], check=False)
        if cp.returncode:
            data['error'] = cp.stderr.decode()
            return data

        xml = etree.fromstring(cp.stdout.decode().strip())
        driver = next((e for e in xml.getchildren() if e.tag == 'driver'), None)
        drivers = [e.text for e in driver.getchildren()] if driver is not None else []

        node_info = await self.middleware.call('vm.device.retrieve_node_information', xml)
        return {
            **node_info,
            'drivers': drivers,
            'available': node_info['iommu_group']['number'] and all(
                d == 'vfio-pci' for d in drivers
            ),
            'error': 'Unable to determine iommu group' if not node_info['iommu_group']['number'] else None,
        }

    async def passthrough_device_choices(self):
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

    async def pptdev_choices(self):
        return await self.passthrough_device_choices()
