import collections
import contextlib
import os.path
import pathlib
import re

from .pci import get_pci_device_class, SENSITIVE_PCI_DEVICE_TYPES


RE_DEVICE_NAME = re.compile(r'(\w+):(\w+):(\w+).(\w+)')


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
