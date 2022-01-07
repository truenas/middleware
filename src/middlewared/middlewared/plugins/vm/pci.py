import re
from xml.etree import ElementTree as etree

from middlewared.schema import accepts, Bool, Dict, List, Ref, returns, Str
from middlewared.service import CallError, private, Service
from middlewared.utils import run

from .utils import get_virsh_command_args


RE_IOMMU_ENABLED = re.compile(r'QEMU.*if IOMMU is enabled.*:\s*PASS.*')


class VMDeviceService(Service):

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
        Str('error', null=True, required=True),
        register=True,
    ))
    async def passthrough_device(self, device):
        """
        Retrieve details about `device` PCI device.
        """
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
        driver = next((e for e in list(xml) if e.tag == 'driver'), None)
        drivers = [e.text for e in list(driver)] if driver is not None else []

        node_info = await self.middleware.call('vm.device.retrieve_node_information', xml)
        error_str = ''
        if not node_info['iommu_group'].get('number'):
            error_str += 'Unable to determine iommu group\n'
        if any(not node_info['capability'].get(k) for k in ('domain', 'bus', 'slot', 'function')):
            error_str += 'Unable to determine PCI device address\n'

        return {
            **node_info,
            'drivers': drivers,
            'available': not error_str and all(d == 'vfio-pci' for d in drivers),
            'error': f'Following errors were found with the device:\n{error_str}' if error_str else None,
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

    @accepts()
    @returns(Ref('passthrough_device_choices'))
    async def pptdev_choices(self):
        """
        Available choices for PCI passthru device.
        """
        return await self.passthrough_device_choices()
