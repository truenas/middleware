from truenas_pylibvirt.device import (
    NICDevice, PCIDevice, FilesystemDevice, USBDevice,
)

from middlewared.api.current import (
    ContainerNICDevice, ContainerPCIDevice,
    ContainerUSBDevice, ContainerFilesystemDevice,
)
from middlewared.utils.libvirt.filesystem import FilesystemDelegate
from middlewared.utils.libvirt.nic import NICDelegate
from middlewared.utils.libvirt.pci import PCIDelegate
from middlewared.utils.libvirt.usb import USBDelegate


class ContainerNICDelegate(NICDelegate):

    @property
    def nic_choices_endpoint(self):
        return 'container.device.nic_attach_choices'

    @property
    def schema_model(self):
        return ContainerNICDevice


class ContainerPCIDelegate(PCIDelegate):

    @property
    def schema_model(self):
        return ContainerPCIDevice


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
        ('NIC', NICDevice, ContainerNICDelegate),
        ('USB', USBDevice, ContainerUSBDelegate),
        ('PCI', PCIDevice, ContainerPCIDelegate),
        ('FILESYSTEM', FilesystemDevice, ContainerFilesystemDelegate),
    ):
        await middleware.call('container.device.register_pylibvirt_device', device_key, device_klass, delegate_klass)
