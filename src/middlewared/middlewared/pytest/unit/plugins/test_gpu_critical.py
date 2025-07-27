import textwrap

import pytest
from unittest.mock import patch, MagicMock

from middlewared.utils.gpu import get_gpus


DEVICE_DATA = {
    '0000:17:00.0': {
        'PCI_ID': '1AF4:1050',
        'ID_VENDOR_FROM_DATABASE': 'NVIDIA Corporation',
        'ID_PCI_SUBCLASS_FROM_DATABASE': 'VGA compatible controller',
        'PCI_SLOT_NAME': '0000:17:00.0',
    },
    '0000:17:00.1': {
        'PCI_ID': '1AF4:1050',
        'ID_VENDOR_FROM_DATABASE': 'NVIDIA Corporation',
        'ID_PCI_SUBCLASS_FROM_DATABASE': 'Audio device',
        'PCI_SLOT_NAME': '0000:17:00.1',
    },
    '0000:00:1f.4': {
        'PCI_ID': '1AF4:1050',
        'ID_VENDOR_FROM_DATABASE': 'Intel Corporation',
        'ID_PCI_SUBCLASS_FROM_DATABASE': 'SMBus',
        'PCI_SLOT_NAME': '0000:00:1f.4',
    },
}


@pytest.mark.parametrize(
    'ls_pci,gpu_pci_id,child_ids,iommu_group,uses_system_critical_devices,critical_reason',
    [
        (
            textwrap.dedent('''
                0000:17:00.0 VGA compatible controller: NVIDIA Corporation TU117GL [T400 4GB] (rev a1)
                0000:17:00.1 Audio device: NVIDIA Corporation Device 10fa (rev a1)
            '''),
            '0000:17:00.0',
            ['0000:17:00.1'],
            {
                '0000:17:00.1': {
                    'number': 9,
                    'addresses': [],
                    'critical': False
                },
                '0000:17:00.0': {
                    'number': 9,
                    'addresses': [],
                    'critical': False
                },
            },
            False,
            None
        ),
        (
            textwrap.dedent('''
                0000:17:00.0 VGA compatible controller: NVIDIA Corporation TU117GL [T400 4GB] (rev a1)
                0000:17:00.1 Audio device: NVIDIA Corporation Device 10fa (rev a1)
                0000:00:1f.4 SMBus: Intel Corporation C620 Series Chipset Family SMBus (rev 09)
            '''),
            '0000:17:00.0',
            ['0000:17:00.1', '0000:00:1f.4'],
            {
                '0000:17:00.1': {
                    'number': 9,
                    'addresses': [],
                    'critical': False
                },
                '0000:17:00.0': {
                    'number': 9,
                    'addresses': [],
                    'critical': False
                },
                '0000:00:1f.4': {
                    'number': 31,
                    'addresses': [],
                    'critical': True
                },
            },
            True,
            ('Devices sharing memory management: SMBus (0000:00:1f.4)\n'
             'Devices sharing memory management in same IOMMU group: SMBus (0000:00:1f.4)')
        ),
        (
            textwrap.dedent('''
                0000:17:00.0 VGA compatible controller: NVIDIA Corporation TU117GL [T400 4GB] (rev a1)
                0000:17:00.1 Audio device: NVIDIA Corporation Device 10fa (rev a1)
                0000:00:1f.4 SMBus: Intel Corporation C620 Series Chipset Family SMBus (rev 09)
            '''),
            '0000:17:00.0',
            ['0000:17:00.1'],
            {
                '0000:17:00.1': {
                    'number': 10,
                    'addresses': [],
                    'critical': False
                },
                '0000:17:00.0': {
                    'number': 9,
                    'addresses': [],
                    'critical': False
                },
                '0000:00:1f.4': {
                    'number': 9,
                    'addresses': [],
                    'critical': True
                },
            },
            True,
            'Devices sharing memory management in same IOMMU group: VGA compatible controller (0000:17:00.0)'
        ),
        (
            textwrap.dedent('''
                0000:17:00.0 VGA compatible controller: NVIDIA Corporation TU117GL [T400 4GB] (rev a1)
                0000:17:00.1 Audio device: NVIDIA Corporation Device 10fa (rev a1)
                0000:00:1f.4 SMBus: Intel Corporation C620 Series Chipset Family SMBus (rev 09)
            '''),
            '0000:17:00.0',
            ['0000:17:00.1'],
            {
                '0000:17:00.1': {
                    'number': 9,
                    'addresses': [],
                    'critical': False
                },
                '0000:17:00.0': {
                    'number': 10,
                    'addresses': [],
                    'critical': False
                },
                '0000:00:1f.4': {
                    'number': 9,
                    'addresses': [],
                    'critical': True
                },
            },
            True,
            'Devices sharing memory management in same IOMMU group: Audio device (0000:17:00.1)'
        )
    ]
)
def test_critical_gpu(
    ls_pci, gpu_pci_id, child_ids, iommu_group, uses_system_critical_devices, critical_reason
):
    with patch('middlewared.utils.gpu.pyudev.Devices.from_name', MagicMock()) as from_name_mock:
        udev_mock = MagicMock()
        udev_mock.get = lambda key, default: DEVICE_DATA[gpu_pci_id].get(key, default)
        udev_mock.parent.children = [DEVICE_DATA[child_id] for child_id in child_ids]
        from_name_mock.return_value = udev_mock
        with patch('middlewared.utils.gpu.subprocess.Popen', MagicMock()) as popen_mock:
            comm_mock = MagicMock()
            comm_mock.returncode = 0
            comm_mock.communicate.return_value = ls_pci.strip().encode(), b''
            popen_mock.return_value = comm_mock

            with patch('middlewared.utils.gpu.get_iommu_groups_info', lambda *args, **kwargs: iommu_group):
                gpus = get_gpus()[0]
                assert gpus['uses_system_critical_devices'] == uses_system_critical_devices
                assert gpus['critical_reason'] == critical_reason
