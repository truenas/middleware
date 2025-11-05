from truenas_pylibvirt.device import (
    CDROMDevice, DisplayDevice, NICDevice, PCIDevice, DiskStorageDevice, RawStorageDevice, USBDevice,
)

from middlewared.api.current import (
    VMCDROMDevice, VMDisplayDevice, VMNICDevice, VMPCIDevice, VMDiskDevice, VMRAWDevice, VMUSBDevice,
)
from middlewared.service_exception import ValidationErrors
from middlewared.utils.crypto import generate_string
from middlewared.utils.libvirt.cdrom import CDROMDelegate
from middlewared.utils.libvirt.display import DisplayDelegate
from middlewared.utils.libvirt.nic import NICDelegate
from middlewared.utils.libvirt.pci import PCIDelegate
from middlewared.utils.libvirt.storage_devices import DiskDelegate, RAWDelegate
from middlewared.utils.libvirt.usb import USBDelegate


def validate_serial_field(
    device: dict,
    verrors: ValidationErrors,
    old: dict | None = None,
    instance: dict | None = None,
    update: bool = True,
) -> None:
    if update is False:
        device['attributes']['serial'] = generate_string(8)
    elif not device['attributes'].get('serial'):
        # As this is a json field, ensure that some consumer does not remove this value, in that case
        # we preserve the original value
        device['attributes']['serial'] = old['attributes']['serial']
    elif device['attributes']['serial'] != old['attributes']['serial']:
        verrors.add('attributes.serial', 'This field is read-only.')


class VMCDROMDelegate(CDROMDelegate):

    @property
    def schema_model(self):
        return VMCDROMDevice


class VMDisplayDelegate(DisplayDelegate):

    @property
    def schema_model(self):
        return VMDisplayDevice


class VMNICDelegate(NICDelegate):

    @property
    def nic_choices_endpoint(self):
        return 'vm.device.nic_attach_choices'

    @property
    def schema_model(self):
        return VMNICDevice


class VMPCIDelegate(PCIDelegate):

    @property
    def schema_model(self):
        return VMPCIDevice


class VMRAWDelegate(RAWDelegate):

    @property
    def schema_model(self):
        return VMRAWDevice

    def validate_middleware(
        self,
        device: dict,
        verrors: ValidationErrors,
        old: dict | None = None,
        instance: dict | None = None,
        update: bool = True,
    ) -> None:
        super().validate_middleware(device, verrors, old, instance, update)
        validate_serial_field(device, verrors, old, instance, update)


class VMDiskDelegate(DiskDelegate):

    @property
    def schema_model(self):
        return VMDiskDevice

    def validate_middleware(
        self,
        device: dict,
        verrors: ValidationErrors,
        old: dict | None = None,
        instance: dict | None = None,
        update: bool = True,
    ) -> None:
        super().validate_middleware(device, verrors, old, instance, update)
        validate_serial_field(device, verrors, old, instance, update)


class VMUSBDelegate(USBDelegate):

    @property
    def schema_model(self):
        return VMUSBDevice


async def setup(middleware):
    for device_key, device_klass, delegate_klass in (
        ('CDROM', CDROMDevice, VMCDROMDelegate),
        ('DISK', DiskStorageDevice, VMDiskDelegate),
        ('RAW', RawStorageDevice, VMRAWDelegate),
        ('NIC', NICDevice, VMNICDelegate),
        ('USB', USBDevice, VMUSBDelegate),
        ('PCI', PCIDevice, VMPCIDelegate),
        ('DISPLAY', DisplayDevice, VMDisplayDelegate),
    ):
        await middleware.call('vm.device.register_pylibvirt_device', device_key, device_klass, delegate_klass)
