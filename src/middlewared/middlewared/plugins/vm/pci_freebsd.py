import re

from middlewared.service import CallError, Service
from middlewared.utils import run

from .pci_base import PCIInfoBase


RE_AMDVI = re.compile(br'vmm\.amdvi\.enable: 1')
RE_PCICONF_PPTDEVS = re.compile(r'^(' + re.escape('ppt') + '[0-9]+@pci.*:)(([0-9]+:){2}[0-9]+).*$', flags=re.I)
RE_VT_D = re.compile(br'DMAR')


class VMDeviceService(Service, PCIInfoBase):

    class Config:
        namespace = 'vm.device'

    iommu_enable = None
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

    async def passthrough_device_choices(self):
        return await self.pptdev_choices()

    async def passthrough_device(self, device):
        choices = await self.pptdev_choices()
        if device not in choices:
            return {
                'available': False,
                'error': 'Unable to locate device',
            }
        else:
            return choices[device]

    async def iommu_enabled(self):
        if self.iommu_enable is not None:
            return self.iommu_enable

        for key, value in {
            'VT-d': {'cmd_args': ['/usr/sbin/acpidump', '-t'], 'pattern': RE_VT_D},
            'amdvi': {'cmd_args': ['/sbin/sysctl', '-i', 'hw.vmm.amdvi.enable'], 'pattern': RE_AMDVI}
        }.items():
            sp = await run(*value['cmd_args'], check=False)
            if sp.returncode:
                raise CallError(f'Failed to check support for iommu ({key}): {sp.stderr.decode()}')
            else:
                if value['pattern'].search(sp.stdout):
                    self.iommu_enable = True
                    break
        else:
            self.iommu_enable = False

        return self.iommu_enable
