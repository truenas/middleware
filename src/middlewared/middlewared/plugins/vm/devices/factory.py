from truenas_pylibvirt.device import (
    CDROMDevice, DisplayDevice, NICDevice, PCIDevice, DiskStorageDevice, RawStorageDevice, USBDevice,
)

from .cdrom import CDROMDelegate
from .display import DisplayDelegate
from .device_factory import DeviceFactory
from .nic import NICDelegate
from .pci import PCIDelegate
from .storage_devices import DiskDelegate, RAWDelegate
from .usb import USBDelegate


device_factory = DeviceFactory()
for device_key, device_klass, delegate_klass in (
    ('CDROM', CDROMDevice, CDROMDelegate),
    ('DISK', DiskStorageDevice, DiskDelegate),
    ('RAW', RawStorageDevice, RAWDelegate),
    ('NIC', NICDevice, NICDelegate),
    ('USB', USBDevice, USBDelegate),
    ('PCI', PCIDevice, PCIDelegate),
    ('DISPLAY', DisplayDevice, DisplayDelegate),
):
    device_factory.register(device_key, device_klass, delegate_klass)
