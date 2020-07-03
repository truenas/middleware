from middlewared.service import Service

from .pci_base import PCIInfoBase


class VMDeviceService(Service, PCIInfoBase):

    def get_iommu_type(self):
        raise NotImplementedError

    def pptdev_choices(self):
        raise NotImplementedError
