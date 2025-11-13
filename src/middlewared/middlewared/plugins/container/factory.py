from truenas_pylibvirt.device import FilesystemDevice, GPUDevice, NICDevice, USBDevice

from middlewared.api.current import (
    ContainerFilesystemDevice, ContainerGPUDevice, ContainerNICDevice, ContainerUSBDevice,
)
from middlewared.utils.libvirt.filesystem import FilesystemDelegate
from middlewared.utils.libvirt.gpu import GPUDelegate
from middlewared.utils.libvirt.nic import NICDelegate
from middlewared.utils.libvirt.usb import USBDelegate


class ContainerNICDelegate(NICDelegate):

    @property
    def nic_choices_endpoint(self):
        return 'container.device.nic_attach_choices'

    @property
    def schema_model(self):
        return ContainerNICDevice


class ContainerUSBDelegate(USBDelegate):

    @property
    def schema_model(self):
        return ContainerUSBDevice


class ContainerFilesystemDelegate(FilesystemDelegate):

    @property
    def schema_model(self):
        return ContainerFilesystemDevice


class ContainerGPUDelegate(GPUDelegate):

    @property
    def schema_model(self):
        return ContainerGPUDevice


async def setup(middleware):
    for device_key, device_klass, delegate_klass in (
        ('FILESYSTEM', FilesystemDevice, ContainerFilesystemDelegate),
        ('GPU', GPUDevice, ContainerGPUDelegate),
        ('NIC', NICDevice, ContainerNICDelegate),
        ('USB', USBDevice, ContainerUSBDelegate),
    ):
        await middleware.call('container.device.register_pylibvirt_device', device_key, device_klass, delegate_klass)
