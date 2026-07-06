import logging

import pytest

from middlewared.plugins.system_advanced.gpu import validate_gpu_pci_ids
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service.context import ServiceContext
from middlewared.service_exception import ValidationErrors

AVAILABLE_GPUS = [
    {
        'addr': {
            'pci_slot': '0000:09:00.0',
            'domain': '0000',
            'bus': '09',
            'slot': '00'
        },
        'description': 'Red Hat, Inc. GPU',
        'devices': [
            {
                'pci_id': '1AF4:1050',
                'pci_slot': '0000:09:00.0',
                'vm_pci_slot': 'pci_0000_09_00_0'
            }
        ],
        'vendor': None,
        'uses_system_critical_devices': False,
        'available_to_host': False
    },
    {
        'addr': {
            'pci_slot': '0000:02:00.0',
            'domain': '0000',
            'bus': '09',
            'slot': '00'
        },
        'description': 'Red Hat, Inc. GPU',
        'devices': [
            {
                'pci_id': '1AF4:1050',
                'pci_slot': '0000:02:00.0',
                'vm_pci_slot': 'pci_0000_02_00_0'
            }
        ],
        'vendor': None,
        'uses_system_critical_devices': True,
        'available_to_host': True
    }
]


@pytest.mark.parametrize('gpu_pci_ids,errors', [
    (['0000:09:00.0'], []),
    (['0000:09:00.0'], []),
    (['0000:02:00.0'], ['0000:02:00.0 GPU pci slot(s) consists of devices which cannot be isolated from host.']),
])
@pytest.mark.asyncio
async def test_valid_isolated_gpu(gpu_pci_ids, errors):
    m = Middleware()
    m['device.get_gpus'] = lambda *args: AVAILABLE_GPUS

    context = ServiceContext(m, logging.getLogger('test'))
    verrors = ValidationErrors()
    verrors = await validate_gpu_pci_ids(context, gpu_pci_ids, verrors, 'test')
    assert [e.errmsg for e in verrors.errors] == errors
