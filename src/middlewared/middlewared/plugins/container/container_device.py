from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerDeviceEntry, ContainerDeviceCreate, ContainerDeviceUpdate, ContainerDeviceDeleteOptions,
    ContainerDeviceCreateArgs, ContainerDeviceCreateResult,
    ContainerDeviceUpdateArgs, ContainerDeviceUpdateResult,
    ContainerDeviceDeleteArgs, ContainerDeviceDeleteResult,
    ContainerDeviceNicAttachChoicesArgs, ContainerDeviceNicAttachChoices, ContainerDeviceNicAttachChoicesResult,
    ContainerDeviceUsbChoicesArgs, ContainerDeviceUsbChoicesResult, USBPassthroughDevice,
    ContainerDeviceGpuChoicesArgs, ContainerDeviceGpuChoicesResult,
)
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.service import GenericCRUDService, private, ValidationErrors
from middlewared.utils.libvirt.device_factory import DeviceFactory
from middlewared.utils.types import AuditCallback

from .container_device_choices import nic_attach_choices, usb_choices, gpu_choices
from .container_device_crud import ContainerDeviceServicePart

if TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ('ContainerDeviceService',)


class ContainerDeviceService(GenericCRUDService[ContainerDeviceEntry]):

    class Config:
        namespace = 'container.device'
        cli_namespace = 'service.container.device'
        role_prefix = 'CONTAINER_DEVICE'
        entry = ContainerDeviceEntry
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self.device_factory = DeviceFactory(middleware)
        self._svc_part = ContainerDeviceServicePart(self.context, self.device_factory)

    @api_method(
        ContainerDeviceCreateArgs, ContainerDeviceCreateResult,
        audit='Container device create',
        audit_extended=lambda data: f'{data["attributes"]["dtype"]}',
        check_annotations=True,
    )
    async def do_create(self, data: ContainerDeviceCreate) -> ContainerDeviceEntry:
        """Create a new device for the container of id `container`."""
        return await self._svc_part.do_create(data)

    @api_method(
        ContainerDeviceUpdateArgs, ContainerDeviceUpdateResult,
        audit='Container device update', audit_callback=True,
        check_annotations=True,
    )
    async def do_update(
        self, audit_callback: AuditCallback, id_: int, data: ContainerDeviceUpdate,
    ) -> ContainerDeviceEntry:
        """Update a container device of `id`."""
        return await self._svc_part.do_update(id_, data, audit_callback=audit_callback)

    @api_method(
        ContainerDeviceDeleteArgs, ContainerDeviceDeleteResult,
        audit='Container device delete', audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(
        self, audit_callback: AuditCallback, id_: int, options: ContainerDeviceDeleteOptions,
    ) -> bool:
        """Delete a container device of `id`."""
        return await self._svc_part.do_delete(id_, options, audit_callback=audit_callback)

    @api_method(
        ContainerDeviceNicAttachChoicesArgs, ContainerDeviceNicAttachChoicesResult,
        roles=['CONTAINER_DEVICE_READ'], check_annotations=True,
    )
    def nic_attach_choices(self) -> ContainerDeviceNicAttachChoices:
        """Available choices for NIC Attach attribute."""
        return nic_attach_choices(self.context)

    @api_method(
        ContainerDeviceUsbChoicesArgs, ContainerDeviceUsbChoicesResult,
        roles=['CONTAINER_DEVICE_READ'], check_annotations=True,
    )
    def usb_choices(self) -> dict[str, USBPassthroughDevice]:
        """Available choices for USB passthrough devices."""
        return usb_choices()

    @api_method(
        ContainerDeviceGpuChoicesArgs, ContainerDeviceGpuChoicesResult,
        roles=['CONTAINER_DEVICE_READ'], check_annotations=True,
    )
    async def gpu_choices(self) -> dict[str, str]:
        """Available choices for GPU devices."""
        return await gpu_choices(self.context)

    @private
    async def validate_path_field(
        self, verrors: ValidationErrors, schema: str, path: str,
    ) -> None:
        await check_path_resides_within_volume(verrors, self.middleware, schema, path)
