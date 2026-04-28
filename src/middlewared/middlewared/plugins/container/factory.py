from __future__ import annotations

from typing import TYPE_CHECKING

from truenas_pylibvirt.device import FilesystemDevice, GPUDevice, NICDevice, USBDevice

from middlewared.api.current import (
    ContainerFilesystemDevice,
    ContainerGPUDevice,
    ContainerNICDevice,
    ContainerUSBDevice,
)
from middlewared.utils.libvirt.filesystem import FilesystemDelegate
from middlewared.utils.libvirt.gpu import GPUDelegate
from middlewared.utils.libvirt.nic import NICDelegate
from middlewared.utils.libvirt.usb import USBDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class ContainerNICDelegate(NICDelegate):

    @property
    def nic_choices_endpoint(self) -> str:
        return 'container.device.nic_attach_choices'

    @property
    def schema_model(self) -> type[ContainerNICDevice]:
        return ContainerNICDevice


class ContainerUSBDelegate(USBDelegate):

    @property
    def schema_model(self) -> type[ContainerUSBDevice]:
        return ContainerUSBDevice


class ContainerFilesystemDelegate(FilesystemDelegate):

    @property
    def schema_model(self) -> type[ContainerFilesystemDevice]:
        return ContainerFilesystemDevice


class ContainerGPUDelegate(GPUDelegate):

    @property
    def schema_model(self) -> type[ContainerGPUDevice]:
        return ContainerGPUDevice


async def setup(middleware: Middleware) -> None:
    device_factory = middleware.services.container.device.device_factory
    for device_key, device_klass, delegate_klass in (
        ('FILESYSTEM', FilesystemDevice, ContainerFilesystemDelegate),
        ('GPU', GPUDevice, ContainerGPUDelegate),
        ('NIC', NICDevice, ContainerNICDelegate),
        ('USB', USBDevice, ContainerUSBDelegate),
    ):
        device_factory.register(device_key, device_klass, delegate_klass)
