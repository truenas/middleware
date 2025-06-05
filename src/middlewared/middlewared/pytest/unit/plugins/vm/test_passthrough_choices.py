from unittest.mock import Mock

import pytest

from middlewared.plugins.vm.pci import VMDeviceService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('pcidevs,results', [
    (
        Mock(
            sys_name='0000:00:00.0',
            attributes={'class': b'0x060000'},
            properties={
                'ID_PCI_SUBCLASS_FROM_DATABASE': 'Host bridge',
                'DRIVER': None,
                'ID_MODEL_FROM_DATABASE': 'Sky Lake-E DMI3 Registers',
                'ID_VENDOR_FROM_DATABASE': 'Intel Corporation',
            }
        ),
        {
            'capability': {
                'class': '0x060000',
                'domain': '0',
                'bus': '0',
                'slot': '0',
                'function': '0',
                'product': 'Sky Lake-E DMI3 Registers',
                'vendor': 'Intel Corporation'
            },
            'controller_type': 'Host bridge',
            'critical': True,
            'iommu_group': {
                'number': 27,
                'addresses': [
                    {
                        'domain': '0x0000',
                        'bus': '0x00',
                        'slot': '0x00',
                        'function': '0x0'
                    }
                ]
            },
            'available': False,
            'drivers': [],
            'error': None,
            'device_path': '/sys/bus/pci/devices/0000:00:00.0',
            'reset_mechanism_defined': False,
            'description': "0000:00:00.0 'Host bridge': Sky Lake-E DMI3 Registers by 'Intel Corporation'"
        }
    ),
    (
        Mock(
            sys_name='0000:00:04.0',
            attributes={'class': b'0x088000'},
            properties={
                'ID_PCI_SUBCLASS_FROM_DATABASE': 'System peripheral',
                'DRIVER': 'ioatdma',
                'ID_MODEL_FROM_DATABASE': 'Sky Lake-E CBDMA Registers',
                'ID_VENDOR_FROM_DATABASE': 'Intel Corporation',
            }
        ),
        {
            'capability': {
                'class': '0x088000',
                'domain': '0',
                'bus': '0',
                'slot': '4',
                'function': '0',
                'product': 'Sky Lake-E CBDMA Registers',
                'vendor': 'Intel Corporation'
            },
            'controller_type': 'System peripheral',
            'critical': False,
            'iommu_group': {
                'number': 28,
                'addresses': [
                    {
                        'domain': '0x0000',
                        'bus': '0x00',
                        'slot': '0x04',
                        'function': '0x0'
                    }
                ]
            },
            'available': False,
            'drivers': ['ioatdma'],
            'error': None,
            'device_path': '/sys/bus/pci/devices/0000:00:04.0',
            'reset_mechanism_defined': False,
            'description': "0000:00:04.0 'System peripheral': Sky Lake-E CBDMA Registers by 'Intel Corporation'"
        }
    ),
])
def test__get_pci_device_details(pcidevs, results):
    iommu_info = {
        '0000:00:00.0': {
            'number': 27,
            'addresses': [
                {
                    'domain': '0x0000',
                    'bus': '0x00',
                    'slot': '0x00',
                    'function': '0x0'
                }
            ],
        },
        '0000:00:04.0': {
            'number': 28,
            'addresses': [
                {
                    'domain': '0x0000',
                    'bus': '0x00',
                    'slot': '0x04',
                    'function': '0x0'
                }
            ],
        }
    }
    assert VMDeviceService(Middleware()).get_pci_device_details(pcidevs, iommu_info) == results
