from middlewared.pytest.unit.helpers import load_compound_service


VMDeviceService = load_compound_service('vm.device')

AVAILABLE_GPUs = [
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
    }
]
IOMMU_GROUPS = {
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
    '0000:17:0e.2': {
        'number': 46,
        'addresses': [
            {
                'domain': '0x0000',
                'bus': '0x17',
                'slot': '0x0e',
                'function': '0x2'
            },
            {
                'domain': '0x0000',
                'bus': '0x17',
                'slot': '0x0e',
                'function': '0x0'
            }
        ]
    },
    '0000:17:0e.0': {
        'number': 46,
        'addresses': [
            {
                'domain': '0x0000',
                'bus': '0x17',
                'slot': '0x0e',
                'function': '0x2'
            },
            {
                'domain': '0x0000',
                'bus': '0x17',
                'slot': '0x0e',
                'function': '0x0'
            }
        ]
    },
    '0000:18:0e.2': {
        'number': 47,
        'addresses': [
            {
                'domain': '0x0000',
                'bus': '0x18',
                'slot': '0x0e',
                'function': '0x2'
            },
            {
                'domain': '0x0000',
                'bus': '0x18',
                'slot': '0x0e',
                'function': '0x0'
            }
        ]
    },
    '0000:18:0e.0': {
        'number': 47,
        'addresses': [
            {
                'domain': '0x0000',
                'bus': '0x18',
                'slot': '0x0e',
                'function': '0x2'
            },
            {
                'domain': '0x0000',
                'bus': '0x18',
                'slot': '0x0e',
                'function': '0x0'
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
}
