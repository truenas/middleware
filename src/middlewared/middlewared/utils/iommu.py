import collections
import contextlib
import os.path
import pathlib
import re


RE_DEVICE_NAME = re.compile(r'(\w+):(\w+):(\w+).(\w+)')
# get capability classes for relevant pci devices from
# https://github.com/pciutils/pciutils/blob/3d2d69cbc55016c4850ab7333de8e3884ec9d498/lib/header.h#L1429
SENSITIVE_PCI_DEVICE_TYPES = {
    '0x0604': 'PCI Bridge',
    '0x0601': 'ISA Bridge',
    '0x0500': 'RAM memory',
    '0x0c05': 'SMBus',
    '0x0600': 'Host bridge',
}


def get_pci_device_class(pci_path: str) -> str:
    with contextlib.suppress(FileNotFoundError):
        with open(os.path.join(pci_path, 'class'), 'r') as r:
            return r.read().strip()

    return ''


def get_iommu_groups_info(get_critical_info: bool = False) -> dict[str, dict]:
    addresses = collections.defaultdict(list)
    final = dict()
    with contextlib.suppress(FileNotFoundError):
        for i in pathlib.Path('/sys/kernel/iommu_groups').glob('*/devices/*'):
            if not i.is_dir() or not i.parent.parent.name.isdigit() or not RE_DEVICE_NAME.fullmatch(i.name):
                continue

            iommu_group = int(i.parent.parent.name)
            dbs, func = i.name.split('.')
            dom, bus, slot = dbs.split(':')
            addresses[iommu_group].append({
                'domain': f'0x{dom}',
                'bus': f'0x{bus}',
                'slot': f'0x{slot}',
                'function': f'0x{func}',
            })
            final[i.name] = {
                'number': iommu_group,
                'addresses': addresses[iommu_group],
            }
            if get_critical_info:
                final[i.name]['critical'] = any(
                    k.lower() in get_pci_device_class(os.path.join('/sys/bus/pci/devices', i.name))
                    for k in SENSITIVE_PCI_DEVICE_TYPES.keys()
                )

    return final
