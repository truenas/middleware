from middlewared.service import accepts, private, ServicePartBase


class PCIInfoBase(ServicePartBase):

    @accepts()
    async def pptdev_choices(self):
        """
        Available choices for PCI passthru device.
        """

    @private
    async def get_iommu_type(self):
        raise NotImplementedError
