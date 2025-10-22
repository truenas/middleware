from truenas_pylibvirt.device import (
    NICDevice, PCIDevice, DiskStorageDevice, FilesystemDevice, RawStorageDevice, USBDevice,
)

from middlewared.api.current import (
    ContainerNICDevice, ContainerPCIDevice, ContainerDiskDevice,
    ContainerRAWDevice, ContainerUSBDevice, ContainerFilesystemDevice,
)
from middlewared.utils.libvirt.filesystem import FilesystemDelegate
from middlewared.utils.libvirt.nic import NICDelegate
from middlewared.utils.libvirt.pci import PCIDelegate
from middlewared.utils.libvirt.storage_devices import DiskDelegate, RAWDelegate
from middlewared.utils.libvirt.usb import USBDelegate


class ContainerNICDelegate(NICDelegate):

    @property
    def schema_model(self):
        return ContainerNICDevice


class ContainerPCIDelegate(PCIDelegate):

    @property
    def schema_model(self):
        return ContainerPCIDevice


class ContainerRAWDelegate(RAWDelegate):

    @property
    def schema_model(self):
        return ContainerRAWDevice


class ContainerDiskDelegate(DiskDelegate):

    @property
    def schema_model(self):
        return ContainerDiskDevice


class ContainerUSBDelegate(USBDelegate):

    @property
    def schema_model(self):
        return ContainerUSBDevice


class ContainerFilesystemDelegate(FilesystemDelegate):

    @property
    def schema_model(self):
        return ContainerFilesystemDevice


async def setup(middleware):
    for device_key, device_klass, delegate_klass in (
        ('DISK', DiskStorageDevice, ContainerDiskDelegate),
        ('RAW', RawStorageDevice, ContainerRAWDelegate),
        ('NIC', NICDevice, ContainerNICDelegate),
        ('USB', USBDevice, ContainerUSBDelegate),
        ('PCI', PCIDevice, ContainerPCIDelegate),
        ('FILESYSTEM', FilesystemDevice, ContainerFilesystemDelegate),
    ):
        await middleware.call('container.device.register_pylibvirt_device', device_key, device_klass, delegate_klass)
