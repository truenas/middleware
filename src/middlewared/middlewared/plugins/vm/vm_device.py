from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    USBPassthroughDevice, USBPassthroughInfo,
    VMDeviceCreate, VMDeviceConvert, VMDeviceDeleteOptions, VMDeviceEntry, VMDeviceUpdate,
    VMDevicePassthroughDevice, VMDevicePassthroughInfo, VMDeviceVirtualSize,
    VMDeviceCreateArgs, VMDeviceCreateResult,
    VMDeviceUpdateArgs, VMDeviceUpdateResult,
    VMDeviceDeleteArgs, VMDeviceDeleteResult,
    VMDeviceConvertArgs, VMDeviceConvertResult,
    VMDeviceVirtualSizeArgs, VMDeviceVirtualSizeResult,
    VMDeviceBindChoicesArgs, VMDeviceBindChoicesResult,
    VMDeviceDiskChoicesArgs, VMDeviceDiskChoicesResult,
    VMDeviceIommuEnabledArgs, VMDeviceIommuEnabledResult,
    VMDeviceIotypeChoicesArgs, VMDeviceIotypeChoicesResult, VMDeviceIotypeChoices,
    VMDeviceNicAttachChoicesArgs, VMDeviceNicAttachChoicesResult, VMDeviceNicAttachChoices,
    VMDevicePassthroughDeviceArgs, VMDevicePassthroughDeviceResult,
    VMDevicePassthroughDeviceChoicesArgs, VMDevicePassthroughDeviceChoicesResult,
    VMDeviceUsbControllerChoicesArgs, VMDeviceUsbControllerChoicesResult,
    VMDeviceUsbPassthroughDeviceArgs, VMDeviceUsbPassthroughDeviceResult,
    VMDeviceUsbPassthroughChoicesArgs, VMDeviceUsbPassthroughChoicesResult,
)
from middlewared.job import Job
from middlewared.service import GenericCRUDService, job, private, ValidationErrors
from middlewared.utils.libvirt.device_factory import DeviceFactory

from .vm_device_convert import convert_disk, virtual_size_impl
from .vm_device_pci import (
    iommu_enabled as _iommu_enabled,
    passthrough_device as _passthrough_device,
    passthrough_device_choices as _passthrough_device_choices,
)
from .vm_device_crud import VMDeviceServicePart, validate_display_devices
from .vm_device_usb import (
    usb_controller_choices as _usb_controller_choices,
    usb_passthrough_device as _usb_passthrough_device,
    usb_passthrough_choices as _usb_passthrough_choices,
)
from .vm_device_info import (
    disk_choices as _disk_choices,
    iotype_choices as _iotype_choices,
    nic_attach_choices as _nic_attach_choices,
    bind_choices as _bind_choices,
)
from .vm_device_utils import validate_path_field

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware
    from middlewared.utils.types import AuditCallback


__all__ = ('VMDeviceService',)


class VMDeviceService(GenericCRUDService[VMDeviceEntry]):

    class Config:
        namespace = 'vm.device'
        cli_namespace = 'service.vm.device'
        role_prefix = 'VM_DEVICE'
        entry = VMDeviceEntry

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self.device_factory = DeviceFactory(self.middleware)
        self._svc_part = VMDeviceServicePart(self.context, self.device_factory)

    @api_method(
        VMDeviceCreateArgs, VMDeviceCreateResult,
        audit='VM device create',
        audit_extended=lambda data: f'{data["attributes"]["dtype"]}',
        check_annotations=True,
    )
    async def do_create(self, data: VMDeviceCreate) -> VMDeviceEntry:
        """
        Create a new device for the VM of id `vm`.

        If `attributes.dtype` is the `RAW` type and a new raw file is to be created, `attributes.exists` will be
        passed as false. This means the API handles creating the raw file and raises the appropriate exception if
        file creation fails.

        If `attributes.dtype` is of `DISK` type and a new Zvol is to be created, `attributes.create_zvol` will be
        passed as true with valid `attributes.zvol_name` and `attributes.zvol_volsize` values.
        """
        return await self._svc_part.do_create(data)

    @api_method(
        VMDeviceUpdateArgs, VMDeviceUpdateResult,
        audit='VM device update',
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(self, audit_callback: AuditCallback, id_: int, data: VMDeviceUpdate) -> VMDeviceEntry:
        """
        Update a VM device of `id`.

        Pass `attributes.size` to resize a `dtype` `RAW` device. The raw file will be resized.
        """
        return await self._svc_part.do_update(id_, data, audit_callback=audit_callback)

    @api_method(
        VMDeviceDeleteArgs, VMDeviceDeleteResult,
        audit='VM device delete',
        audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(self, audit_callback: AuditCallback, id_: int, options: VMDeviceDeleteOptions) -> bool:
        """
        Delete a VM device of `id`.
        """
        return await self._svc_part.do_delete(id_, options, audit_callback=audit_callback)

    @api_method(VMDeviceBindChoicesArgs, VMDeviceBindChoicesResult, roles=['VM_DEVICE_READ'], check_annotations=True)
    async def bind_choices(self) -> dict[str, str]:
        """
        Available choices for Bind attribute.
        """
        return await _bind_choices(self.context)

    @api_method(
        VMDeviceConvertArgs, VMDeviceConvertResult,
        roles=['VM_DEVICE_WRITE'],
        audit='Converting disk image',
        check_annotations=True,
    )
    @job(lock='vm.device.convert', lock_queue_size=1)
    def convert(self, job: Job, data: VMDeviceConvert) -> bool:
        """
        Convert between disk images and ZFS volumes. Supported disk image formats \
        are qcow2, qed, raw, vdi, vhdx, and vmdk. The conversion direction is determined \
        automatically based on file extension.
        """
        return convert_disk(self.context, job, data)

    @api_method(VMDeviceDiskChoicesArgs, VMDeviceDiskChoicesResult, roles=['VM_DEVICE_READ'], check_annotations=True)
    async def disk_choices(self) -> dict[str, str]:
        """
        Returns disk choices for device type "DISK".
        """
        return await _disk_choices(self.context)

    @api_method(
        VMDeviceIommuEnabledArgs, VMDeviceIommuEnabledResult,
        roles=['VM_DEVICE_READ'], check_annotations=True,
    )
    def iommu_enabled(self) -> bool:
        """Returns "true" if iommu is enabled, "false" otherwise"""
        return _iommu_enabled()

    @api_method(
        VMDeviceIotypeChoicesArgs, VMDeviceIotypeChoicesResult, roles=['VM_DEVICE_READ'], check_annotations=True
    )
    def iotype_choices(self) -> VMDeviceIotypeChoices:
        """
        IO-type choices for storage devices.
        """
        return _iotype_choices()

    @api_method(
        VMDeviceNicAttachChoicesArgs, VMDeviceNicAttachChoicesResult,
        roles=['VM_DEVICE_READ'], check_annotations=True,
    )
    async def nic_attach_choices(self) -> VMDeviceNicAttachChoices:
        """
        Available choices for NIC Attach attribute.
        """
        return await _nic_attach_choices(self.context)

    @api_method(
        VMDevicePassthroughDeviceArgs, VMDevicePassthroughDeviceResult,
        roles=['VM_DEVICE_READ'], check_annotations=True,
    )
    def passthrough_device(self, device: str) -> VMDevicePassthroughDevice:
        """Retrieve details about `device` PCI device"""
        return _passthrough_device(device)

    @api_method(
        VMDevicePassthroughDeviceChoicesArgs, VMDevicePassthroughDeviceChoicesResult,
        roles=['VM_DEVICE_READ'], check_annotations=True,
    )
    def passthrough_device_choices(self) -> VMDevicePassthroughInfo:
        """Available choices for PCI passthru devices"""
        return _passthrough_device_choices()

    @api_method(
        VMDeviceUsbControllerChoicesArgs, VMDeviceUsbControllerChoicesResult,
        roles=['VM_DEVICE_READ'], check_annotations=True,
    )
    def usb_controller_choices(self) -> dict[str, str]:
        """Retrieve USB controller type choices"""
        return _usb_controller_choices()

    @api_method(
        VMDeviceUsbPassthroughDeviceArgs, VMDeviceUsbPassthroughDeviceResult,
        roles=['VM_DEVICE_READ'], check_annotations=True,
    )
    def usb_passthrough_device(self, device: str) -> USBPassthroughDevice:
        """Retrieve details about `device` USB device."""
        return _usb_passthrough_device(device)

    @api_method(
        VMDeviceUsbPassthroughChoicesArgs, VMDeviceUsbPassthroughChoicesResult,
        roles=['VM_DEVICE_READ'], check_annotations=True,
    )
    def usb_passthrough_choices(self) -> USBPassthroughInfo:
        """Available choices for USB passthrough devices."""
        return _usb_passthrough_choices()

    @api_method(
        VMDeviceVirtualSizeArgs, VMDeviceVirtualSizeResult,
        roles=['VM_DEVICE_READ'], check_annotations=True,
    )
    def virtual_size(self, data: VMDeviceVirtualSize) -> int:
        """
        Get the virtual size of a disk image using qemu-img info.
        """
        return virtual_size_impl('vm.device.virtual_size', data.path)

    @private
    async def validate_display_devices(self, verrors: ValidationErrors, vm_instance: dict[str, typing.Any]) -> None:
        await validate_display_devices(verrors, vm_instance)

    @private
    async def validate_path_field(self, verrors: ValidationErrors, schema: str, path: str) -> None:
        await validate_path_field(self.context, verrors, schema, path)
