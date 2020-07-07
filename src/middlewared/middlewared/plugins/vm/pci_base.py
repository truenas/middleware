from middlewared.service import accepts, ServicePartBase


class PCIInfoBase(ServicePartBase):

    @accepts()
    async def pptdev_choices(self):
        """
        Available choices for PCI passthru device.
        """

    @accepts()
    async def iommu_enabled(self):
        """
        Returns "true" if iommu is enabled, "false" otherwise
        """
