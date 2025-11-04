from truenas_pylibvirt.device import (
    CDROMDevice, DisplayDevice, NICDevice, PCIDevice, DiskStorageDevice, RawStorageDevice, USBDevice,
)

from middlewared.api.current import (
    VMCDROMDevice, VMDisplayDevice, VMNICDevice, VMPCIDevice, VMDiskDevice, VMRAWDevice, VMUSBDevice,
)
from middlewared.utils.libvirt.cdrom import CDROMDelegate
from middlewared.utils.libvirt.display import DisplayDelegate
from middlewared.utils.libvirt.nic import NICDelegate
from middlewared.utils.libvirt.pci import PCIDelegate
from middlewared.utils.libvirt.storage_devices import DiskDelegate, RAWDelegate
from middlewared.utils.libvirt.usb import USBDelegate


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


class VMDiskDelegate(DiskDelegate):

    @property
    def schema_model(self):
        return VMDiskDevice


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
