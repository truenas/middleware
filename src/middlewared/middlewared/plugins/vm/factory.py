from truenas_pylibvirt.device import (
    CDROMDevice, DisplayDevice, NICDevice, PCIDevice, DiskStorageDevice, RawStorageDevice, USBDevice,
)

from middlewared.utils.libvirt.cdrom import CDROMDelegate
from middlewared.utils.libvirt.display import DisplayDelegate
from middlewared.utils.libvirt.nic import NICDelegate
from middlewared.utils.libvirt.pci import PCIDelegate
from middlewared.utils.libvirt.storage_devices import DiskDelegate, RAWDelegate
from middlewared.utils.libvirt.usb import USBDelegate


async def setup(middleware):
    for device_key, device_klass, delegate_klass in (
        ('CDROM', CDROMDevice, CDROMDelegate),
        ('DISK', DiskStorageDevice, DiskDelegate),
        ('RAW', RawStorageDevice, RAWDelegate),
        ('NIC', NICDevice, NICDelegate),
        ('USB', USBDevice, USBDelegate),
        ('PCI', PCIDevice, PCIDelegate),
        ('DISPLAY', DisplayDevice, DisplayDelegate),
    ):
        await middleware.call('vm.device.register_pylibvirt_device', device_key, device_klass, delegate_klass)
