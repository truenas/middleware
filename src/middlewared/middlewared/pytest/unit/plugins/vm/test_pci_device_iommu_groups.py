from pathlib import PosixPath
from unittest.mock import Mock, patch

from middlewared.utils.iommu import get_iommu_groups_info


DEVICES_PATH = [
    PosixPath('/sys/kernel/iommu_groups/55/devices/0000:64:0a.1'),
    PosixPath('/sys/kernel/iommu_groups/83/devices/0000:b2:0f.0'),
    PosixPath('/sys/kernel/iommu_groups/17/devices/0000:00:04.0'),
    PosixPath('/sys/kernel/iommu_groups/45/devices/0000:16:0e.2'),
    PosixPath('/sys/kernel/iommu_groups/45/devices/0000:16:0e.0'),
    PosixPath('/sys/kernel/iommu_groups/45a/devices/0000:16:0e.7'),
    PosixPath('/sys/kernel/iommu_groups/45/devices/test_file')
]
IOMMU_GROUPS = {
    '0000:64:0a.1': {
        'number': 55,
        'addresses': [
            {
                'domain': '0x0000',
                'bus': '0x64',
                'slot': '0x0a',
                'function': '0x1'
            }
        ]
    },
    '0000:b2:0f.0': {
        'number': 83,
        'addresses': [
            {
                'domain': '0x0000',
                'bus': '0xb2',
                'slot': '0x0f',
                'function': '0x0'
            }
        ]
    },
    '0000:00:04.0': {
        'number': 17,
        'addresses': [
            {
                'domain': '0x0000',
                'bus': '0x00',
                'slot': '0x04',
                'function': '0x0'
            }
        ]
    },
    '0000:16:0e.2': {
        'number': 45,
        'addresses': [
            {
                'domain': '0x0000',
                'bus': '0x16',
                'slot': '0x0e',
                'function': '0x2'
            },
            {
                'domain': '0x0000',
                'bus': '0x16',
                'slot': '0x0e',
                'function': '0x0'
            }
        ]
    },
    '0000:16:0e.0': {
        'number': 45,
        'addresses': [
            {
                'domain': '0x0000',
                'bus': '0x16',
                'slot': '0x0e',
                'function': '0x2'
            },
            {
                'domain': '0x0000',
                'bus': '0x16',
                'slot': '0x0e',
                'function': '0x0'
            }
        ]
    },
}


def test_iommu_groups():
    with patch('middlewared.utils.iommu.pathlib.PosixPath.is_dir', Mock(return_value=True)):
        with patch('middlewared.utils.iommu.pathlib.Path.glob', Mock(return_value=DEVICES_PATH)):
            assert get_iommu_groups_info() == IOMMU_GROUPS
