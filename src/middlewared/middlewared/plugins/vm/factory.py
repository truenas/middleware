from __future__ import annotations

from typing import TYPE_CHECKING, Any

from truenas_pylibvirt.device import (
    CDROMDevice,
    DiskStorageDevice,
    DisplayDevice,
    NICDevice,
    PCIDevice,
    RawStorageDevice,
    USBDevice,
)

from middlewared.api.current import (
    VMCDROMDevice,
    VMDiskDevice,
    VMDisplayDevice,
    VMNICDevice,
    VMPCIDevice,
    VMRAWDevice,
    VMUSBDevice,
)
from middlewared.service_exception import ValidationErrors
from middlewared.utils.crypto import generate_string
from middlewared.utils.libvirt.cdrom import CDROMDelegate
from middlewared.utils.libvirt.display import DisplayDelegate
from middlewared.utils.libvirt.nic import NICDelegate
from middlewared.utils.libvirt.pci import PCIDelegate
from middlewared.utils.libvirt.storage_devices import DiskDelegate, RAWDelegate
from middlewared.utils.libvirt.usb import USBDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


def validate_storage_fields(
    device: dict[str, Any],
    verrors: ValidationErrors,
    old: dict[str, Any] | None = None,
    instance: dict[str, Any] | None = None,
    update: bool = True,
) -> None:
    if update is False:
        device["attributes"]["serial"] = generate_string(8)
    elif old is not None:
        if not device["attributes"].get("serial"):
            # As this is a json field, ensure that some consumer does not remove this value, in that case
            # we preserve the original value
            device["attributes"]["serial"] = old["attributes"]["serial"]
        elif device["attributes"]["serial"] != old["attributes"]["serial"]:
            verrors.add("attributes.serial", "This field is read-only.")

    logical_sectorsize = device["attributes"].get("logical_sectorsize")
    physical_sectorsize = device["attributes"].get("physical_sectorsize")
    if logical_sectorsize and physical_sectorsize and logical_sectorsize > physical_sectorsize:
        # https://patchew.org/QEMU/1508343141-31835-1-git-send-email-pbonzini%40redhat.com/1508343141-31835-30
        # -git-send-email-pbonzini%40redhat.com
        verrors.add(
            "attributes.logical_sectorsize",
            "Logical sector size cannot be greater than physical sector size."
        )


class VMCDROMDelegate(CDROMDelegate):

    @property
    def schema_model(self) -> type[VMCDROMDevice]:
        return VMCDROMDevice


class VMDisplayDelegate(DisplayDelegate):

    @property
    def schema_model(self) -> type[VMDisplayDevice]:
        return VMDisplayDevice


class VMNICDelegate(NICDelegate):

    @property
    def nic_choices_endpoint(self) -> str:
        return "vm.device.nic_attach_choices"

    @property
    def schema_model(self) -> type[VMNICDevice]:
        return VMNICDevice


class VMPCIDelegate(PCIDelegate):

    @property
    def schema_model(self) -> type[VMPCIDevice]:
        return VMPCIDevice


class VMRAWDelegate(RAWDelegate):

    @property
    def schema_model(self) -> type[VMRAWDevice]:
        return VMRAWDevice

    def validate_middleware(
        self,
        device: dict[str, Any],
        verrors: ValidationErrors,
        old: dict[str, Any] | None = None,
        instance: dict[str, Any] | None = None,
        update: bool = True,
    ) -> None:
        super().validate_middleware(device, verrors, old, instance, update)
        validate_storage_fields(device, verrors, old, instance, update)

        attrs = device["attributes"]
        if update is False and attrs.get("exists", True) is False and attrs.get("size"):
            # We would be creating the file in this case, so let's validate that
            # size is a multiple of logical sectorsize or 512
            logical_sectorsize = attrs.get("logical_sectorsize") or 512
            if attrs["size"] % logical_sectorsize != 0:
                verrors.add(
                    "attributes.size",
                    f"Size must be a multiple of logical sector size ({logical_sectorsize!r} bytes)."
                )


class VMDiskDelegate(DiskDelegate):

    @property
    def schema_model(self) -> type[VMDiskDevice]:
        return VMDiskDevice

    def validate_middleware(
        self,
        device: dict[str, Any],
        verrors: ValidationErrors,
        old: dict[str, Any] | None = None,
        instance: dict[str, Any] | None = None,
        update: bool = True,
    ) -> None:
        super().validate_middleware(device, verrors, old, instance, update)
        validate_storage_fields(device, verrors, old, instance, update)


class VMUSBDelegate(USBDelegate):

    @property
    def schema_model(self) -> type[VMUSBDevice]:
        return VMUSBDevice


async def setup(middleware: Middleware) -> None:
    device_factory = middleware.services.vm.device.device_factory
    for device_key, device_klass, delegate_klass in (
        ("CDROM", CDROMDevice, VMCDROMDelegate),
        ("DISK", DiskStorageDevice, VMDiskDelegate),
        ("RAW", RawStorageDevice, VMRAWDelegate),
        ("NIC", NICDevice, VMNICDelegate),
        ("USB", USBDevice, VMUSBDelegate),
        ("PCI", PCIDevice, VMPCIDelegate),
        ("DISPLAY", DisplayDevice, VMDisplayDelegate),
    ):
        device_factory.register(device_key, device_klass, delegate_klass)
