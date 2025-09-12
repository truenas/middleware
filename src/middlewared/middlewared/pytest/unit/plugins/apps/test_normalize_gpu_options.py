
import pytest

from middlewared.plugins.apps.schema_normalization import AppSchemaService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('gpu_list, value, expected', [
    (
        [
            {
                'pci_slot': '0000:00:02.0',
                'addr': {
                    'domain': '0000',
                    'bus': '00',
                    'slot': '02'
                },
                'description': 'Red Hat, Inc. QXL paravirtual graphic card',
                'devices': [
                    {'pci_id': '8086:1237', 'pci_slot': '0000:00:00.0', 'vm_pci_slot': 'pci_0000_00_00_0'},
                    {'pci_id': '8086:7000', 'pci_slot': '0000:00:01.0', 'vm_pci_slot': 'pci_0000_00_01_0'},

                ],
                'vendor': 'NVIDIA',
                'uses_system_critical_devices': True,
                'critical_reason': 'Critical devices found: 0000:00:01.0',
                'available_to_host': True,
                'error': ''
            }
        ],
        {
            'use_all_gpus': True,
            'kfd_device_exists': False,
            'nvidia_gpu_selection': {
                '0000:01:00.0': 'NVIDIA GPU 1',
                '0000:02:00.0': 'NVIDIA GPU 2'
            }
        },
        {
            'use_all_gpus': False,
            'kfd_device_exists': False,
            'nvidia_gpu_selection': {}
        }

    ),
    (
        [
            {
                'pci_slot': '0000:00:02.0',
                'addr': {
                    'domain': '0000',
                    'bus': '00',
                    'slot': '02'
                },
                'description': 'Intel Integrated Graphics',
                'devices': [
                    {'pci_id': '8086:1234', 'pci_slot': '0000:00:00.0', 'vm_pci_slot': 'pci_0000_00_00_0'},
                ],
                'vendor': 'Intel',  # Non-NVIDIA vendor
                'uses_system_critical_devices': True,
                'critical_reason': 'No critical devices.',
                'available_to_host': True,
                'error': ''
            }
        ],
        {
            'use_all_gpus': True,
            'kfd_device_exists': False,
            'nvidia_gpu_selection': {}
        },
        {
            'use_all_gpus': True,
            'kfd_device_exists': False,
            'nvidia_gpu_selection': {}
        }

    ),
    (
        [
            {
                'pci_slot': '0000:00:02.0',
                'addr': {
                    'domain': '0000',
                    'bus': '00',
                    'slot': '02'
                },
                'description': 'NVIDIA GeForce RTX 3080',
                'devices': [
                    {'pci_id': '10de:2206', 'pci_slot': '0000:01:00.0', 'vm_pci_slot': 'pci_0000_01_00_0'},
                ],
                'vendor': 'NVIDIA',  # This GPU is NVIDIA
                'uses_system_critical_devices': True,
                'critical_reason': 'No critical devices.',
                'available_to_host': True,
                'error': ''
            },
            {
                'pci_slot': '0000:00:03.0',
                'addr': {
                    'domain': '0000',
                    'bus': '00',
                    'slot': '03'
                },
                'description': 'AMD Radeon RX 6800',
                'devices': [
                    {'pci_id': '1002:73bf', 'pci_slot': '0000:01:01.0', 'vm_pci_slot': 'pci_0000_01_01_0'},
                ],
                'vendor': 'AMD',  # Non-NVIDIA vendor
                'uses_system_critical_devices': False,
                'critical_reason': 'No critical devices.',
                'available_to_host': True,
                'error': ''
            }
        ],
        {
            'use_all_gpus': True,
            'kfd_device_exists': True,
            'nvidia_gpu_selection': {}
        },
        {
            'use_all_gpus': True,
            'kfd_device_exists': True,
            'nvidia_gpu_selection': {}
        }

    )
])
@pytest.mark.asyncio
async def test_normalize_gpu_option(gpu_list, value, expected):
    middleware = Middleware()
    app_schema_obj = AppSchemaService(middleware)
    middleware['app.gpu_choices_internal'] = lambda *args: gpu_list
    result = await app_schema_obj.normalize_gpu_configuration('', value, '', '')
    assert result is not None
    assert result == expected
