import collections
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
    '0000:00:01.0': {
        'PCI_ID': '8086:1901',
        'ID_VENDOR_FROM_DATABASE': 'Intel Corporation',
        'ID_PCI_SUBCLASS_FROM_DATABASE': 'PCI bridge',
        'PCI_SLOT_NAME': '0000:00:01.0',
    },
    '0000:01:00.0': {
        'PCI_ID': '10DE:2489',
        'ID_VENDOR_FROM_DATABASE': 'NVIDIA Corporation',
        'ID_PCI_SUBCLASS_FROM_DATABASE': 'VGA compatible controller',
        'PCI_SLOT_NAME': '0000:01:00.0',
    },
    '0000:01:00.1': {
        'PCI_ID': '10DE:228B',
        'ID_VENDOR_FROM_DATABASE': 'NVIDIA Corporation',
        'ID_PCI_SUBCLASS_FROM_DATABASE': 'Audio device',
        'PCI_SLOT_NAME': '0000:01:00.1',
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
            False,  # GPU is in different IOMMU group than SMBus
            None
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
            'Devices sharing memory management: SMBus (0000:00:1f.4)'
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
            False,  # GPU is in group 10, SMBus is in group 9 - different groups
            None
        ),
        (
            textwrap.dedent('''
                0000:00:01.0 PCI bridge: Intel Corporation 6th-10th Gen Core Processor PCIe Controller (x16) (rev 07)
                0000:01:00.0 VGA compatible controller: NVIDIA Corporation GA104 [GeForce RTX 3060 Ti] (rev a1)
                0000:01:00.1 Audio device: NVIDIA Corporation GA104 High Definition Audio Controller (rev a1)
            '''),
            '0000:01:00.0',
            ['0000:01:00.1'],  # child_ids not used in new logic
            {
                '0000:00:01.0': {
                    'number': 2,
                    'addresses': [],
                    'critical': False  # Bridge should not be critical
                },
                '0000:01:00.0': {
                    'number': 2,
                    'addresses': [],
                    'critical': False
                },
                '0000:01:00.1': {
                    'number': 2,
                    'addresses': [],
                    'critical': False
                },
            },
            False,
            None
        )
    ]
)
def test_critical_gpu(
    ls_pci, gpu_pci_id, child_ids, iommu_group, uses_system_critical_devices, critical_reason
):
    with patch('middlewared.utils.gpu.pyudev.Devices.from_name', MagicMock()) as from_name_mock:
        def mock_from_name(context, subsystem, device_name):
            udev_mock = MagicMock()
            if device_name in DEVICE_DATA:
                udev_mock.get = lambda key, default: DEVICE_DATA[device_name].get(key, default)
            else:
                # For devices not in DEVICE_DATA, return empty values
                udev_mock.get = lambda key, default: default
            return udev_mock

        from_name_mock.side_effect = mock_from_name

        # Build device_to_class and bus_to_devices from the test data
        device_to_class = {}
        bus_to_devices = collections.defaultdict(list)
        # Parse ls_pci to get device addresses
        gpu_devices = []
        for line in ls_pci.strip().split('\n'):
            if line.strip():
                addr = line.split()[0]
                gpu_devices.append(addr)
                # Add to device_to_class based on device type
                if 'VGA compatible controller' in line:
                    device_to_class[addr] = 0x030000  # VGA
                elif 'Audio device' in line:
                    device_to_class[addr] = 0x040300  # Audio
                elif 'SMBus' in line:
                    device_to_class[addr] = 0x0c0500  # SMBus
                elif 'PCI bridge' in line:
                    device_to_class[addr] = 0x060400  # PCI bridge
                # Add to bus_to_devices
                try:
                    parts = addr.split(':')
                    domain = int(parts[0], 16)
                    bus = int(parts[1], 16)
                    bus_to_devices[(domain, bus)].append(addr)
                except (IndexError, ValueError):
                    pass
        # Mock build_pci_device_cache
        with patch('middlewared.utils.gpu.build_pci_device_cache') as mock_build_cache:
            mock_build_cache.return_value = (device_to_class, bus_to_devices)

            # Mock the bridge analysis functions
            with patch('truenas_pylibvirt.utils.iommu.get_devices_behind_bridge') as mock_get_devices:
                # For bridge 0000:00:01.0, return GPU devices behind it
                def get_devices_side_effect(bridge_addr, bus_to_devices=None, device_to_class=None):
                    if bridge_addr == '0000:00:01.0':
                        return ['0000:01:00.0', '0000:01:00.1']
                    return []
                mock_get_devices.side_effect = get_devices_side_effect

                # Mock build_pci_device_cache for iommu.py
                with patch('truenas_pylibvirt.utils.iommu.build_pci_device_cache') as mock_iommu_build:
                    mock_iommu_build.return_value = (device_to_class, bus_to_devices)

                    with patch('truenas_pylibvirt.utils.iommu.get_pci_device_class') as mock_get_class:
                        def get_class_side_effect(path):
                            # Return appropriate class based on device
                            for addr, class_code in device_to_class.items():
                                if addr in path:
                                    return f'0x{class_code:06x}'
                            return '0x000000'

                        mock_get_class.side_effect = get_class_side_effect

                        # Mock get_iommu_groups_info with pci_build_cache parameter
                        def mock_get_iommu_groups_info(get_critical_info=False, pci_build_cache=None):
                            return iommu_group

                        with patch('middlewared.utils.gpu.get_iommu_groups_info',
                                   side_effect=mock_get_iommu_groups_info):
                            gpus = get_gpus()
                            assert len(gpus) > 0, "No GPUs found"
                            gpu = gpus[0]
                            assert gpu['uses_system_critical_devices'] == uses_system_critical_devices
                            assert gpu['critical_reason'] == critical_reason
