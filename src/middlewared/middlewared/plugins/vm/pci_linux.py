import re

from middlewared.service import CallError, Service
from middlewared.utils import run

from .pci_base import PCIInfoBase


RE_IOMMU_ENABLED = re.compile(r'QEMU.*if IOMMU is enabled.*:\s*PASS.*')


class VMDeviceService(Service, PCIInfoBase):

    async def iommu_enabled(self):
        cp = await run(['virt-host-validate'], check=False)
        if cp.returncode:
            raise CallError(f'Unable to determine if iommu is enabled: %s', cp.stderr.decode())
        return bool(RE_IOMMU_ENABLED.findall(cp.stdout.decode()))

    def pptdev_choices(self):
        raise NotImplementedError
