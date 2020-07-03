import re

from middlewared.service import CallError, Service
from middlewared.utils import run

from .pci_base import PCIInfoBase


RE_PCICONF_PPTDEVS = re.compile(r'^(' + re.escape('ppt') + '[0-9]+@pci.*:)(([0-9]+:){2}[0-9]+).*$', flags=re.I)


class VMDeviceService(Service, PCIInfoBase):

    iommu_type = None
    pptdevs = {}

    async def pptdev_choices(self):
        if self.pptdevs:
            return self.pptdevs

        sp = await run('/usr/sbin/pciconf', '-l', check=False)
        if sp.returncode:
            raise CallError(f'Failed to detect devices available for PCI passthru: {sp.stderr.decode()}')
        else:
            lines = sp.stdout.decode().split('\n')
            for line in lines:
                object = RE_PCICONF_PPTDEVS.match(line)
                if object:
                    pptdev = object.group(2).replace(':', '/')
                    self.pptdevs[pptdev] = pptdev

        return self.pptdevs

    async def get_iommu_type(self):
        if self.iommu_type:
            return self.iommu_type

        for key, value in {
            'VT-d': {'cmd_args': ['/usr/sbin/acpidump', '-t'], 'pattern': br'DMAR'},
            'amdvi': {'cmd_args': ['/sbin/sysctl', '-i', 'hw.vmm.amdvi.enable'], 'pattern': br'vmm\.amdvi\.enable: 1'}
        }.items():
            sp = await run(*value['cmd_args'], check=False)
            if sp.returncode:
                raise CallError(f'Failed to check support for iommu ({key}): {sp.stderr.decode()}')
            else:
                if re.search(value['pattern'], sp.stdout):
                    self.iommu_type = key
                    break

        return self.iommu_type
