import contextlib
import os


# get capability classes for relevant pci devices from
# https://github.com/pciutils/pciutils/blob/3d2d69cbc55016c4850ab7333de8e3884ec9d498/lib/header.h#L1429
SENSITIVE_PCI_DEVICE_TYPES = {
    '0x0604': 'PCI Bridge',
    '0x0601': 'ISA Bridge',
    '0x0500': 'RAM memory',
    '0x0c05': 'SMBus',
}


def get_pci_device_class(pci_path: str) -> str:
    with contextlib.suppress(FileNotFoundError):
        with open(os.path.join(pci_path, 'class'), 'r') as r:
            return r.read().strip()

    return ''
