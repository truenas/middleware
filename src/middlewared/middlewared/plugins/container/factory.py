from __future__ import annotations

from typing import TYPE_CHECKING, Any

from truenas_pylibvirt.device import FilesystemDevice, GPUDevice, NICDevice, USBDevice

from middlewared.api.current import (
    ContainerFilesystemDevice,
    ContainerGPUDevice,
    ContainerNICDevice,
    ContainerUSBDevice,
)
from middlewared.service_exception import ValidationErrors
from middlewared.utils.libvirt.filesystem import FilesystemDelegate
from middlewared.utils.libvirt.gpu import GPUDelegate
from middlewared.utils.libvirt.nic import NICDelegate
from middlewared.utils.libvirt.usb import USBDelegate

from .bridge import BRIDGE_NAME

if TYPE_CHECKING:
    from middlewared.main import Middleware


class ContainerNICDelegate(NICDelegate):

    @property
    def nic_choices_endpoint(self) -> str:
        return 'container.device.nic_attach_choices'

    @property
    def schema_model(self) -> type[ContainerNICDevice]:
        return ContainerNICDevice

    def validate_middleware(
        self,
        device: dict[str, Any],
        verrors: ValidationErrors,
        old: dict[str, Any] | None = None,
        instance: dict[str, Any] | None = None,
        update: bool = True,
    ) -> None:
        # A NIC stored without an attachment is a macvlan on the default-route interface and stays one.
        if not device['attributes']['nic_attach'] and (old is None or old['attributes']['nic_attach']):
            device['attributes']['nic_attach'] = self.middleware.call_sync('lxc.config').bridge or BRIDGE_NAME
        super().validate_middleware(device, verrors, old, instance, update)


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
