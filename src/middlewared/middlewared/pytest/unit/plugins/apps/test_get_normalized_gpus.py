import pytest

from middlewared.plugins.apps.resources_utils import get_normalized_gpu_choices


@pytest.mark.parametrize('all_gpu_info, nvidia_gpus, should_work', [
    (
        [
            {
                'addr': {
                    'pci_slot': '0000:00:02.0',
                    'domain': '0000',
                    'bus': '00',
                    'slot': '02'
                },
                'description': 'Red Hat, Inc. QXL paravirtual graphic card',
                'devices': [
                    {'pci_id': '8086:1237', 'pci_slot': '0000:00:00.0', 'vm_pci_slot': 'pci_0000_00_00_0'},
                    {'pci_id': '8086:7000', 'pci_slot': '0000:00:01.0', 'vm_pci_slot': 'pci_0000_00_01_0'},
                    {'pci_id': '8086:7010', 'pci_slot': '0000:00:01.1', 'vm_pci_slot': 'pci_0000_00_01_1'},
                    {'pci_id': '8086:7113', 'pci_slot': '0000:00:01.3', 'vm_pci_slot': 'pci_0000_00_01_3'},
                ],
                'vendor': None,
                'uses_system_critical_devices': True,
                'critical_reason': 'Critical devices found: 0000:00:01.0',
                'available_to_host': True
            }
        ],
        {},
        True
    ),
    (
        [
            {
                'addr': {
                    'pci_slot': '0000:00:02.0',
                    'domain': '0000',
                    'bus': '00',
                    'slot': '02'
                },
                'description': 'Red Hat, Inc. QXL paravirtual graphic card',
                'devices': [
                    {'pci_id': '8086:1237', 'pci_slot': '0000:00:00.0', 'vm_pci_slot': 'pci_0000_00_00_0'},
                    {'pci_id': '8086:7000', 'pci_slot': '0000:00:01.0', 'vm_pci_slot': 'pci_0000_00_01_0'},
                    {'pci_id': '8086:7010', 'pci_slot': '0000:00:01.1', 'vm_pci_slot': 'pci_0000_00_01_1'},
                    {'pci_id': '8086:7113', 'pci_slot': '0000:00:01.3', 'vm_pci_slot': 'pci_0000_00_01_3'},
                ],
                'vendor': 'NVIDIA',
                'uses_system_critical_devices': True,
                'critical_reason': 'Critical devices found: 0000:00:01.0',
                'available_to_host': True
            }
        ],
        {
            'gpu_uuid': 112,
            'model': 'A6000x2',
            'description': "NVIDIA's A6000 GPU with 2 cores",
            'pci_slot': 11111,
        },
        False
    ),
    (
        [
            {
                'addr': {
                    'pci_slot': '0000:00:02.0',
                    'domain': '0000',
                    'bus': '00',
                    'slot': '02'
                },
                'description': 'Red Hat, Inc. QXL paravirtual graphic card',
                'devices': [
                    {'pci_id': '8086:1237', 'pci_slot': '0000:00:00.0', 'vm_pci_slot': 'pci_0000_00_00_0'},
                    {'pci_id': '8086:7000', 'pci_slot': '0000:00:01.0', 'vm_pci_slot': 'pci_0000_00_01_0'},
                    {'pci_id': '8086:7010', 'pci_slot': '0000:00:01.1', 'vm_pci_slot': 'pci_0000_00_01_1'},
                    {'pci_id': '8086:7113', 'pci_slot': '0000:00:01.3', 'vm_pci_slot': 'pci_0000_00_01_3'},
                ],
                'vendor': 'NVIDIA',
                'uses_system_critical_devices': True,
                'critical_reason': 'Critical devices found: 0000:00:01.0',
                'available_to_host': True
            }
        ],
        {
            'model': 'A6000x2',
            'description': "NVIDIA's A6000 GPU with 2 cores",
            '0000:00:02.0': {
                'gpu_uuid': '112',
            },
        },
        True
    ),
    (
        [
            {
                'addr': {
                    'pci_slot': '0000:00:02.0',
                    'domain': '0000',
                    'bus': '00',
                    'slot': '02'
                },
                'description': 'Red Hat, Inc. QXL paravirtual graphic card',
                'devices': [
                    {'pci_id': '8086:1237', 'pci_slot': '0000:00:00.0', 'vm_pci_slot': 'pci_0000_00_00_0'},
                    {'pci_id': '8086:7000', 'pci_slot': '0000:00:01.0', 'vm_pci_slot': 'pci_0000_00_01_0'},
                    {'pci_id': '8086:7010', 'pci_slot': '0000:00:01.1', 'vm_pci_slot': 'pci_0000_00_01_1'},
                    {'pci_id': '8086:7113', 'pci_slot': '0000:00:01.3', 'vm_pci_slot': 'pci_0000_00_01_3'},
                ],
                'vendor': 'NVIDIA',
                'uses_system_critical_devices': True,
                'critical_reason': 'Critical devices found: 0000:00:01.0',
                'available_to_host': True
            }
        ],
        {
            'model': 'A6000x2',
            'description': "NVIDIA's A6000 GPU with 2 cores",
            '0000:00:02.0': {},
        },
        False
    ),
    (
        [
            {
                'addr': {
                    'pci_slot': '0000:00:02.0',
                    'domain': '0000',
                    'bus': '00',
                    'slot': '02'
                },
                'description': 'Red Hat, Inc. QXL paravirtual graphic card',
                'devices': [
                    {'pci_id': '8086:1237', 'pci_slot': '0000:00:00.0', 'vm_pci_slot': 'pci_0000_00_00_0'},
                    {'pci_id': '8086:7000', 'pci_slot': '0000:00:01.0', 'vm_pci_slot': 'pci_0000_00_01_0'},
                    {'pci_id': '8086:7010', 'pci_slot': '0000:00:01.1', 'vm_pci_slot': 'pci_0000_00_01_1'},
                    {'pci_id': '8086:7113', 'pci_slot': '0000:00:01.3', 'vm_pci_slot': 'pci_0000_00_01_3'},
                ],
                'vendor': 'NVIDIA',
                'uses_system_critical_devices': True,
                'critical_reason': 'Critical devices found: 0000:00:01.0',
                'available_to_host': True
            }
        ],
        {
            'model': 'A6000x2',
            'description': "NVIDIA's A6000 GPU with 2 cores",
            '0000:00:02.0': {
                'gpu_uuid': '1125?as'
            },
        },
        False
    ),
    (
        [
            {
                'addr': {
                    'pci_slot': '0000:00:02.0',
                    'domain': '0000',
                    'bus': '00',
                    'slot': '02'
                },
                'description': 'Red Hat, Inc. QXL paravirtual graphic card',
                'devices': [
                    {'pci_id': '8086:1237', 'pci_slot': '0000:00:00.0', 'vm_pci_slot': 'pci_0000_00_00_0'},
                    {'pci_id': '8086:7000', 'pci_slot': '0000:00:01.0', 'vm_pci_slot': 'pci_0000_00_01_0'},
                    {'pci_id': '8086:7010', 'pci_slot': '0000:00:01.1', 'vm_pci_slot': 'pci_0000_00_01_1'},
                    {'pci_id': '8086:7113', 'pci_slot': '0000:00:01.3', 'vm_pci_slot': 'pci_0000_00_01_3'},
                ],
                'vendor': None,
                'uses_system_critical_devices': True,
                'critical_reason': 'Critical devices found: 0000:00:01.0',
                'available_to_host': False
            }
        ],
        {},
        False
    ),
])
def test_get_normalized_gpus(all_gpu_info, nvidia_gpus, should_work):
    result = get_normalized_gpu_choices(all_gpu_info, nvidia_gpus)
    if should_work:
        assert result[0]['error'] is None
    else:
        assert result[0]['error'] is not None
