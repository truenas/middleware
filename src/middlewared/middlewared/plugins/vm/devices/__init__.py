from .cdrom import CDROM
from .nic import NIC
from .pci import PCI
from .storage_devices import DISK, RAW
from .display import DISPLAY
from .usb import USB

__all__ = ['CDROM', 'DEVICES', 'DISK', 'NIC', 'PCI', 'RAW', 'DISPLAY', 'USB']


DEVICES = {
    device_class.__name__: device_class for device_class in (
        CDROM, DISK, NIC, PCI, RAW, DISPLAY, USB
    )
}
