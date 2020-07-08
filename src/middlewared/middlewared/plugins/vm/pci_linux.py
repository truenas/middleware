import re

from lxml import etree

from middlewared.service import CallError, private, Service
from middlewared.utils import run

from .pci_base import PCIInfoBase


RE_IOMMU_ENABLED = re.compile(r'QEMU.*if IOMMU is enabled.*:\s*PASS.*')


class VMDeviceService(Service, PCIInfoBase):

    class Config:
        namespace = 'vm.device'

    async def iommu_enabled(self):
        cp = await run(['virt-host-validate'], check=False)
        if cp.returncode:
            raise CallError('Unable to determine if iommu is enabled: %s', cp.stderr.decode())
        return bool(RE_IOMMU_ENABLED.findall(cp.stdout.decode()))

    @private
    def retrieve_node_information(self, xml):
        info = {'capability': {}, 'iommu_group': {'number': None, 'addresses': []}}
        capability = next((e for e in xml.getchildren() if e.tag == 'capability' and e.get('type') == 'pci'), None)
        if not capability:
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

    async def passthrough_device_choices(self):
        cp = await run(['virsh', 'nodedev-list', 'pci'], check=False)
        if cp.returncode:
            raise CallError(f'Unable to retrieve PCI devices: {cp.stderr.decode()}')
        pci_devices = [k.strip() for k in cp.stdout.decode().split('\n') if k.strip()]
        mapping = {}
        for pci in pci_devices:
            cp = await run(['virsh', 'nodedev-dumpxml', pci], check=False)
            if cp.returncode:
                self.middleware.logger.debug('Failed to retrieve details for %r: %s', pci, cp.stderr.decode())
                continue
            xml = etree.fromstring(cp.stdout.decode().strip())
            driver = next((e for e in xml.getchildren() if e.tag == 'driver'), None)
            drivers = [e.text for e in driver.getchildren()] if driver is not None else []

            if not driver or (drivers and not all(d == 'vfio-pci' for d in drivers)):
                self.middleware.logger.debug(
                    'Only "vfio-pci" driver is expected to be configured for %r PCI device. Driver(s) found were: %s',
                    pci, ', '.join(drivers)
                )
                continue

            node_info = await self.middleware.call('vm.device.retrieve_node_information', xml)
            if not node_info['iommu_group']['number']:
                self.middleware.logger.debug('Unable to determine iommu group for %r, skipping', pci)
                continue

            mapping[pci] = {**node_info, 'drivers': drivers}

        return mapping

    async def pptdev_choices(self):
        return await self.passthrough_device_choices()
