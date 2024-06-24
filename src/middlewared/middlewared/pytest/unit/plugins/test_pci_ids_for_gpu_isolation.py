import pytest

from unittest.mock import Mock, patch

from middlewared.pytest.unit.helpers import load_compound_service
from middlewared.pytest.unit.middleware import Middleware


SYSTEM_ADVANCED_SERVICE = load_compound_service('system.advanced')
AVAILABLE_GPU = [
    {
        'addr': {
            'pci_slot': '0000:16:0e.0',
            'domain': '0000',
            'bus': '16',
            'slot': '0e'
        },
        'description': 'Red Hat, Inc. Virtio 1.0 GPU',
        'devices': [
            {
                'pci_id': '8086:29C0',
                'pci_slot': '0000:16:0e.0',
                'vm_pci_slot': 'pci_0000_16_0e_0'
            },
            {
                'pci_id': '1AF4:1050',
                'pci_slot': '0000:16:0e.2',
                'vm_pci_slot': 'pci_0000_16_0e_2'
            },
        ],
        'vendor': None,
        'uses_system_critical_devices': False,
        'available_to_host': True
    },
    {
        'addr': {
            'pci_slot': '0000:17:0e.0',
            'domain': '0000',
            'bus': '17',
            'slot': '0e'
        },
        'description': 'Red Hat, Inc. Virtio 1.0 GPU',
        'devices': [
            {
                'pci_id': '8086:29C0',
                'pci_slot': '0000:17:0e.0',
                'vm_pci_slot': 'pci_0000_17_0e_0'
            },
            {
                'pci_id': '1AF4:1050',
                'pci_slot': '0000:17:0e.2',
                'vm_pci_slot': 'pci_0000_17_0e_2'
            },
        ],
        'vendor': None,
        'uses_system_critical_devices': False,
        'available_to_host': False
    },
    {
        'addr': {
            'pci_slot': '0000:18:0e.0',
            'domain': '0000',
            'bus': '18',
            'slot': '0e'
        },
        'description': 'Red Hat, Inc. Virtio 1.0 GPU',
        'devices': [
            {
                'pci_id': '8086:29C0',
                'pci_slot': '0000:18:0e.0',
                'vm_pci_slot': 'pci_0000_18_0e_0'
            },
            {
                'pci_id': '1AF4:1050',
                'pci_slot': '0000:18:0e.2',
                'vm_pci_slot': 'pci_0000_18_0e_2'
            },
        ],
        'vendor': None,
        'uses_system_critical_devices': True,
        'available_to_host': True
    },
    {
        'addr': {
            'pci_slot': '0000:19:0e.0',
            'domain': '0000',
            'bus': '19',
            'slot': '0e'
        },
        'description': 'Red Hat, Inc. Virtio 1.0 GPU',
        'devices': [
            {
                'pci_id': '8086:29C0',
                'pci_slot': '0000:19:0e.0',
                'vm_pci_slot': 'pci_0000_19_0e_0'
            },
            {
                'pci_id': '1AF4:1050',
                'pci_slot': '0000:19:0e.2',
                'vm_pci_slot': 'pci_0000_19_0e_2'
            },
        ],
        'vendor': None,
        'uses_system_critical_devices': True,
        'available_to_host': True
    },
    {
        'addr': {
            'pci_slot': '0000:20:0e.0',
            'domain': '0000',
            'bus': '20',
            'slot': '0e'
        },
        'description': 'Red Hat, Inc. Virtio 1.0 GPU',
        'devices': [
            {
                'pci_id': '8086:29C0',
                'pci_slot': '0000:20:0e.0',
                'vm_pci_slot': 'pci_0000_20_0e_0'
            },
            {
                'pci_id': '1AF4:1050',
                'pci_slot': '0000:20:0e.2',
                'vm_pci_slot': 'pci_0000_20_0e_2'
            },
        ],
        'vendor': None,
        'uses_system_critical_devices': True,
        'available_to_host': True
    },
]

IOMMU_GROUPS = {
    '0000:16:0e.0': {
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
    '0000:16:0e.2': {
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
    '0000:17:0e.0': {
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
    '0000:17:0e.2': {
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
    '0000:18:0e.0': {
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
    '0000:19:0e.0': {
        'number': 46,
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
    '0000:19:0e.2': {
        'number': 18,
        'addresses': [
            {
                'domain': '0x0000',
                'bus': '0x00',
                'slot': '0x04',
                'function': '0x0'
            }
        ]
    },
    '0000:00:04.0': {
        'number': 18,
        'addresses': [
            {
                'domain': '0x0000',
                'bus': '0x00',
                'slot': '0x04',
                'function': '0x0'
            }
        ]
    },
    '0000:20:0e.0': {
        'number': 19,
        'addresses': [
            {
                'domain': '0x0000',
                'bus': '0x00',
                'slot': '0x04',
                'function': '0x0'
            }
        ]
    },
    '0000:00:02.0': {
        'number': 19,
        'addresses': [
            {
                'domain': '0x0000',
                'bus': '0x00',
                'slot': '0x04',
                'function': '0x0'
            }
        ]
    },
}

CRITICAL_GPU_IDS = {
    '/sys/bus/pci/devices/0000:00:02.0': '0x060400',
    '/sys/bus/pci/devices/0000:00:04.0': '0x060100',
}


@pytest.mark.parametrize('isolated_gpu,keys,values', [
    (
        [],
        {
            'Red Hat, Inc. Virtio 1.0 GPU [0000:16:0e.0]',
            'Red Hat, Inc. Virtio 1.0 GPU [0000:17:0e.0]',
        },
        {
            '0000:16:0e.0',
            '0000:17:0e.0'
        }
    ),
    (
        ['0000:18:0e.0'],
        {
            'Red Hat, Inc. Virtio 1.0 GPU [0000:16:0e.0]',
            'Red Hat, Inc. Virtio 1.0 GPU [0000:17:0e.0]',
            'Unknown \'0000:18:0e.0\' slot',
        },
        {
            '0000:16:0e.0',
            '0000:17:0e.0',
            '0000:18:0e.0'
        }
    ),
    (
        ['0000:19:0e.0'],
        {
            'Red Hat, Inc. Virtio 1.0 GPU [0000:16:0e.0]',
            'Red Hat, Inc. Virtio 1.0 GPU [0000:17:0e.0]',
            'Unknown \'0000:19:0e.0\' slot',
        },
        {
            '0000:16:0e.0',
            '0000:17:0e.0',
            '0000:19:0e.0'
        }
    ),
    (
        ['0000:20:0e.0'],
        {
            'Red Hat, Inc. Virtio 1.0 GPU [0000:16:0e.0]',
            'Red Hat, Inc. Virtio 1.0 GPU [0000:17:0e.0]',
            'Unknown \'0000:20:0e.0\' slot',
        },
        {
            '0000:16:0e.0',
            '0000:17:0e.0',
            '0000:20:0e.0'
        }
    ),
    (
        ['0000:21:0e.0'],
        {
            'Red Hat, Inc. Virtio 1.0 GPU [0000:16:0e.0]',
            'Red Hat, Inc. Virtio 1.0 GPU [0000:17:0e.0]',
            'Unknown \'0000:21:0e.0\' slot',
        },
        {
            '0000:16:0e.0',
            '0000:17:0e.0',
            '0000:21:0e.0'
        }
    ),


])
def test_isolate_gpu_choices(isolated_gpu, keys, values):
    m = Middleware()
    m['system.advanced.config'] = lambda *args: {'isolated_gpu_pci_ids': isolated_gpu}
    m['vm.device.get_iommu_groups_info'] = lambda *args: IOMMU_GROUPS
    with patch('middlewared.plugins.system_advanced.gpu.get_gpus', Mock(return_value=AVAILABLE_GPU)):
        with patch('middlewared.plugins.system_advanced.gpu.get_pci_device_class',
                   lambda path: CRITICAL_GPU_IDS.get(path, '0x543100')):
            assert set(SYSTEM_ADVANCED_SERVICE(m).get_gpu_pci_choices().keys()) == keys
            assert set(SYSTEM_ADVANCED_SERVICE(m).get_gpu_pci_choices().values()) == values
