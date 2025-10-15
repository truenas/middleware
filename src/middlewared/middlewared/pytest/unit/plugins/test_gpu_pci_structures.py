"""
Comprehensive tests for various GPU PCI topologies and critical device detection.
Tests include simple cases, bridge scenarios, complex topologies, and edge cases.
"""
import collections

import pytest
from unittest.mock import patch, MagicMock
from truenas_pylibvirt.utils.iommu import get_iommu_groups_info, is_pci_bridge_critical

from middlewared.utils.gpu import get_gpus


# Mock PCI topologies for testing
MOCK_TOPOLOGIES = {
    'simple_gpu_not_critical': {
        'description': 'Simple GPU with audio device, no critical devices',
        'lspci': """
0000:01:00.0 VGA compatible controller: NVIDIA Corporation GA104 [GeForce RTX 3060 Ti] (rev a1)
0000:01:00.1 Audio device: NVIDIA Corporation GA104 High Definition Audio Controller (rev a1)
        """,
        'devices': {
            '0000:01:00.0': {
                'class': '0x030000',  # VGA
                'vendor': 'NVIDIA Corporation',
                'subclass': 'VGA compatible controller',
                'iommu_group': 1,
            },
            '0000:01:00.1': {
                'class': '0x040300',  # Audio
                'vendor': 'NVIDIA Corporation',
                'subclass': 'Audio device',
                'iommu_group': 1,
            },
        },
        'expected_critical': False,
        'expected_reason': None,
    },

    'gpu_with_smbus': {
        'description': 'GPU sharing IOMMU group with SMBus (critical)',
        'lspci': """
0000:01:00.0 VGA compatible controller: NVIDIA Corporation GA104 [GeForce RTX 3060 Ti] (rev a1)
0000:01:00.1 Audio device: NVIDIA Corporation GA104 High Definition Audio Controller (rev a1)
0000:00:1f.4 SMBus: Intel Corporation Sunrise Point-H SMBus (rev 31)
        """,
        'devices': {
            '0000:01:00.0': {
                'class': '0x030000',  # VGA
                'vendor': 'NVIDIA Corporation',
                'subclass': 'VGA compatible controller',
                'iommu_group': 2,
            },
            '0000:01:00.1': {
                'class': '0x040300',  # Audio
                'vendor': 'NVIDIA Corporation',
                'subclass': 'Audio device',
                'iommu_group': 2,
            },
            '0000:00:1f.4': {
                'class': '0x0c0500',  # SMBus
                'vendor': 'Intel Corporation',
                'subclass': 'SMBus',
                'iommu_group': 2,
            },
        },
        'expected_critical': True,
        'expected_reason': 'Devices sharing memory management: SMBus (0000:00:1f.4)',
    },

    'gpu_with_simple_bridge': {
        'description': 'GPU behind PCI bridge with no critical devices',
        'lspci': """
0000:00:01.0 PCI bridge: Intel Corporation 6th-10th Gen Core Processor PCIe Controller (x16) (rev 07)
0000:01:00.0 VGA compatible controller: NVIDIA Corporation GA104 [GeForce RTX 3060 Ti] (rev a1)
0000:01:00.1 Audio device: NVIDIA Corporation GA104 High Definition Audio Controller (rev a1)
        """,
        'devices': {
            '0000:00:01.0': {
                'class': '0x060400',  # PCI Bridge
                'vendor': 'Intel Corporation',
                'subclass': 'PCI bridge',
                'iommu_group': 2,
            },
            '0000:01:00.0': {
                'class': '0x030000',  # VGA
                'vendor': 'NVIDIA Corporation',
                'subclass': 'VGA compatible controller',
                'iommu_group': 2,
            },
            '0000:01:00.1': {
                'class': '0x040300',  # Audio
                'vendor': 'NVIDIA Corporation',
                'subclass': 'Audio device',
                'iommu_group': 2,
            },
        },
        'bridge_devices': {
            '0000:00:01.0': ['0000:01:00.0', '0000:01:00.1'],
        },
        'expected_critical': False,
        'expected_reason': None,
    },

    'gpu_with_bridge_and_critical': {
        'description': 'GPU behind bridge that also has critical device',
        'lspci': """
0000:00:1c.0 PCI bridge: Intel Corporation Sunrise Point-H PCI Express Root Port (rev f1)
0000:02:00.0 VGA compatible controller: NVIDIA Corporation GM107 [GeForce GTX 750 Ti] (rev a2)
0000:02:00.1 Audio device: NVIDIA Corporation GM107 High Definition Audio Controller (rev a1)
0000:02:01.0 SMBus: Intel Corporation C620 Series Chipset Family SMBus (rev 09)
        """,
        'devices': {
            '0000:00:1c.0': {
                'class': '0x060400',  # PCI Bridge
                'vendor': 'Intel Corporation',
                'subclass': 'PCI bridge',
                'iommu_group': 5,
            },
            '0000:02:00.0': {
                'class': '0x030000',  # VGA
                'vendor': 'NVIDIA Corporation',
                'subclass': 'VGA compatible controller',
                'iommu_group': 5,
            },
            '0000:02:00.1': {
                'class': '0x040300',  # Audio
                'vendor': 'NVIDIA Corporation',
                'subclass': 'Audio device',
                'iommu_group': 5,
            },
            '0000:02:01.0': {
                'class': '0x0c0500',  # SMBus
                'vendor': 'Intel Corporation',
                'subclass': 'SMBus',
                'iommu_group': 5,
            },
        },
        'bridge_devices': {
            '0000:00:1c.0': ['0000:02:00.0', '0000:02:00.1', '0000:02:01.0'],
        },
        'expected_critical': True,
        'expected_reason': 'Devices sharing memory management: PCI bridge (0000:00:1c.0), SMBus (0000:02:01.0)',
    },

    'chained_bridges_no_critical': {
        'description': 'GPU behind chained bridges with no critical devices',
        'lspci': """
0000:00:01.0 PCI bridge: Intel Corporation PCIe Root Port (rev 07)
0000:01:00.0 PCI bridge: PLX Technology PEX 8747 48-Lane PCIe Switch (rev ca)
0000:02:00.0 VGA compatible controller: AMD Radeon Pro W6800 (rev c3)
0000:02:00.1 Audio device: AMD Navi 21 HDMI Audio (rev 01)
        """,
        'devices': {
            '0000:00:01.0': {
                'class': '0x060400',  # PCI Bridge
                'vendor': 'Intel Corporation',
                'subclass': 'PCI bridge',
                'iommu_group': 3,
            },
            '0000:01:00.0': {
                'class': '0x060400',  # PCI Bridge (PLX switch)
                'vendor': 'PLX Technology',
                'subclass': 'PCI bridge',
                'iommu_group': 3,
            },
            '0000:02:00.0': {
                'class': '0x030000',  # VGA
                'vendor': 'AMD',
                'subclass': 'VGA compatible controller',
                'iommu_group': 3,
            },
            '0000:02:00.1': {
                'class': '0x040300',  # Audio
                'vendor': 'AMD',
                'subclass': 'Audio device',
                'iommu_group': 3,
            },
        },
        'bridge_devices': {
            '0000:00:01.0': ['0000:01:00.0'],
            '0000:01:00.0': ['0000:02:00.0', '0000:02:00.1'],
        },
        'expected_critical': False,
        'expected_reason': None,
    },

    'multi_gpu_different_groups': {
        'description': 'Multiple GPUs in different IOMMU groups',
        'lspci': """
0000:01:00.0 VGA compatible controller: NVIDIA Corporation GA104 [GeForce RTX 3060 Ti] (rev a1)
0000:01:00.1 Audio device: NVIDIA Corporation GA104 High Definition Audio Controller (rev a1)
0000:02:00.0 VGA compatible controller: NVIDIA Corporation TU117 [GeForce GTX 1650] (rev a1)
0000:02:00.1 Audio device: NVIDIA Corporation TU117 High Definition Audio Controller (rev a1)
        """,
        'devices': {
            '0000:01:00.0': {
                'class': '0x030000',  # VGA
                'vendor': 'NVIDIA Corporation',
                'subclass': 'VGA compatible controller',
                'iommu_group': 10,
            },
            '0000:01:00.1': {
                'class': '0x040300',  # Audio
                'vendor': 'NVIDIA Corporation',
                'subclass': 'Audio device',
                'iommu_group': 10,
            },
            '0000:02:00.0': {
                'class': '0x030000',  # VGA
                'vendor': 'NVIDIA Corporation',
                'subclass': 'VGA compatible controller',
                'iommu_group': 11,
            },
            '0000:02:00.1': {
                'class': '0x040300',  # Audio
                'vendor': 'NVIDIA Corporation',
                'subclass': 'Audio device',
                'iommu_group': 11,
            },
        },
        'expected_critical': False,
        'expected_reason': None,
        'gpu_count': 2,
    },

    'integrated_gpu_critical': {
        'description': 'Intel integrated GPU sharing group with host bridge',
        'lspci': """
0000:00:00.0 Host bridge: Intel Corporation 8th Gen Core Processor Host Bridge/DRAM Registers (rev 07)
0000:00:02.0 VGA compatible controller: Intel Corporation UHD Graphics 630 (rev 02)
        """,
        'devices': {
            '0000:00:00.0': {
                'class': '0x060000',  # Host bridge
                'vendor': 'Intel Corporation',
                'subclass': 'Host bridge',
                'iommu_group': 0,
            },
            '0000:00:02.0': {
                'class': '0x030000',  # VGA
                'vendor': 'Intel Corporation',
                'subclass': 'VGA compatible controller',
                'iommu_group': 0,
            },
        },
        'expected_critical': True,
        'expected_reason': 'Devices sharing memory management: Host bridge (0000:00:00.0)',
    },
}


def create_mock_pyudev_device(device_info):
    """Create a mock pyudev device with the specified attributes."""
    mock = MagicMock()
    mock.get = MagicMock(side_effect=lambda key, default='': {
        'PCI_ID': device_info.get('pci_id', ''),
        'ID_VENDOR_FROM_DATABASE': device_info.get('vendor', ''),
        'ID_PCI_SUBCLASS_FROM_DATABASE': device_info.get('subclass', ''),
        'PCI_SLOT_NAME': device_info.get('address', ''),
    }.get(key, default))
    return mock


@pytest.mark.parametrize('topology_name', list(MOCK_TOPOLOGIES.keys()))
def test_gpu_pci_topology(topology_name):
    """Test various GPU PCI topologies for correct critical device detection."""
    topology = MOCK_TOPOLOGIES[topology_name]

    # Build IOMMU groups info
    iommu_groups = {}
    for addr, device_info in topology['devices'].items():
        iommu_groups[addr] = {
            'number': device_info['iommu_group'],
            'addresses': [],
            'critical': False,  # Will be determined by get_iommu_groups_info logic
        }

    # No longer need to mock subprocess since we're using direct sysfs reading

    # Mock pyudev
    def mock_from_name(context, subsystem, device_addr):
        if device_addr in topology['devices']:
            device_info = topology['devices'][device_addr].copy()
            device_info['address'] = device_addr
            return create_mock_pyudev_device(device_info)
        return create_mock_pyudev_device({})

    with patch('middlewared.utils.gpu.pyudev.Devices.from_name', side_effect=mock_from_name):
        # Mock both get_pci_device_class and build_pci_device_cache
        with patch('middlewared.utils.iommu.get_pci_device_class') as mock_get_class:
            def mock_get_class_code(path):
                for addr, info in topology['devices'].items():
                    if addr in path:
                        return info['class']  # Return string as expected
                return '0x000000'
            mock_get_class.side_effect = mock_get_class_code

            # Build the cache data from topology
            device_to_class = {}
            bus_to_devices = collections.defaultdict(list)
            for addr, info in topology['devices'].items():
                device_to_class[addr] = int(info['class'], 16)
                try:
                    parts = addr.split(':')
                    domain = int(parts[0], 16)
                    bus = int(parts[1], 16)
                    bus_to_devices[(domain, bus)].append(addr)
                except (IndexError, ValueError):
                    pass

            # Mock build_pci_device_cache for both iommu.py and gpu.py
            with patch('middlewared.utils.iommu.build_pci_device_cache') as mock_build_cache_iommu:
                mock_build_cache_iommu.return_value = (device_to_class, bus_to_devices)

                with patch('middlewared.utils.gpu.build_pci_device_cache') as mock_build_cache_gpu:
                    mock_build_cache_gpu.return_value = (device_to_class, bus_to_devices)

                    # Mock bridge device detection with new signature
                    def mock_get_devices_behind_bridge(bridge_addr, bus_to_devices=None, device_to_class=None):
                        return topology.get('bridge_devices', {}).get(bridge_addr, [])

                    with patch('middlewared.utils.iommu.get_devices_behind_bridge',
                               side_effect=mock_get_devices_behind_bridge):
                        # Mock pathlib for IOMMU group scanning
                        with patch('middlewared.utils.iommu.pathlib.Path') as mock_path:
                            # Mock the IOMMU groups directory structure
                            mock_iommu_paths = []
                            for addr, info in topology['devices'].items():
                                mock_device = MagicMock()
                                mock_device.is_dir.return_value = True
                                mock_device.name = addr
                                mock_device.parent.parent.name = str(info['iommu_group'])
                                mock_iommu_paths.append(mock_device)
                            mock_path.return_value.glob.return_value = mock_iommu_paths

                            # Get IOMMU groups with critical info
                            iommu_groups = get_iommu_groups_info(get_critical_info=True)

                            # Mock the IOMMU groups for get_gpus - need to handle the pci_build_cache parameter
                            def mock_get_iommu_groups_info(get_critical_info=False, pci_build_cache=None):
                                return iommu_groups

                            with patch('middlewared.utils.gpu.get_iommu_groups_info',
                                       side_effect=mock_get_iommu_groups_info):

                                # Get GPUs
                                gpus = get_gpus()

                                # Check expectations
                                expected_gpu_count = topology.get('gpu_count', 1)
                                assert len(gpus) == expected_gpu_count, \
                                    f"Expected {expected_gpu_count} GPU(s), got {len(gpus)}"

                                if expected_gpu_count == 1:
                                    gpu = gpus[0]
                                    assert gpu['uses_system_critical_devices'] == topology['expected_critical'], \
                                        f"Expected critical={topology['expected_critical']}, " \
                                        f"got {gpu['uses_system_critical_devices']}"

                                    if topology['expected_critical']:
                                        assert gpu['critical_reason'] == topology['expected_reason'], \
                                            f"Expected reason: {topology['expected_reason']}, " \
                                            f"got: {gpu['critical_reason']}"
                                    else:
                                        assert gpu['critical_reason'] is None


def test_error_handling():
    """Test error handling for invalid configurations."""
    # Test with no GPUs
    with patch('middlewared.utils.gpu.build_pci_device_cache') as mock_build_cache:
        # Return empty caches (no devices)
        mock_build_cache.return_value = ({}, {})

        with patch('middlewared.utils.gpu.get_iommu_groups_info', return_value={}):
            gpus = get_gpus()
            assert len(gpus) == 0


def test_circular_bridge_reference():
    """Test handling of circular bridge references (error case)."""
    # This should not cause infinite recursion
    with patch('middlewared.utils.iommu.get_devices_behind_bridge') as mock_get_devices:
        # Create circular reference: bridge A -> bridge B -> bridge A
        def circular_devices(bridge_addr):
            if bridge_addr == '0000:00:01.0':
                return ['0000:01:00.0']
            elif bridge_addr == '0000:01:00.0':
                return ['0000:00:01.0']  # Circular!
            return []

        def circular_devices_wrapper(bridge_addr, bus_to_devices=None, device_to_class=None):
            return circular_devices(bridge_addr)

        mock_get_devices.side_effect = circular_devices_wrapper

        with patch('middlewared.utils.iommu.get_pci_device_class') as mock_get_class:
            mock_get_class.return_value = '0x060400'  # All are bridges

            # This should not hang or crash
            result = is_pci_bridge_critical('0000:00:01.0')
            assert result is False  # Should handle gracefully
