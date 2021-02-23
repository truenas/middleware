from middlewared.schema import Str
from middlewared.service import accepts, ServicePartBase


class PCIInfoBase(ServicePartBase):

    @accepts()
    async def pptdev_choices(self):
        """
        Available choices for PCI passthru device.
        """

    @accepts()
    async def passthrough_device_choices(self):
        """
        Available choices for PCI passthru devices.
        """

    @accepts()
    async def iommu_enabled(self):
        """
        Returns "true" if iommu is enabled, "false" otherwise
        """

    @accepts(Str('device'))
    async def passthrough_device(self, device):
        """
        Retrieve details about `device` PCI device.
        """
