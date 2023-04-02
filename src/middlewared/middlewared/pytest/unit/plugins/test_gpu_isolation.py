import pytest

from middlewared.pytest.unit.helpers import load_compound_service
from middlewared.pytest.unit.middleware import Middleware
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
ADVANCED_SVC = load_compound_service('system.advanced')


@pytest.mark.parametrize('gpu_pci_ids,errors', [
    (['0000:09:00.0'], []),
    (['0000:09:00.0'], []),
    (['0000:02:00.0'], ['0000:02:00.0 GPU pci slot(s) consists of devices which cannot be isolated from host.']),
])
@pytest.mark.asyncio
async def test_valid_isolated_gpu(gpu_pci_ids, errors):
    m = Middleware()
    m['device.get_gpus'] = lambda *args: AVAILABLE_GPUS

    system_advance_svc = ADVANCED_SVC(m)
    verrors = ValidationErrors()
    verrors = await system_advance_svc.validate_gpu_pci_ids(gpu_pci_ids, verrors, 'test')
    assert [e.errmsg for e in verrors.errors] == errors
