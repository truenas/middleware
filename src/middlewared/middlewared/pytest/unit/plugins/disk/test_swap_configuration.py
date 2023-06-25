import pytest

from unittest.mock import AsyncMock, patch, Mock

from middlewared.plugins.disk_.swap_configure import DiskService
from middlewared.pytest.unit.middleware import Middleware


ALL_PARTITIONS = {
    'sda': [
        {
            'name': 'sda1',
            'partition_type': '21686148-6449-6e6f-744e-656564454649',
            'partition_uuid': 'ee6e4763-1e61-466d-9972-e3c46dfc4a1c',
            'disk': 'sda',
            'size': 1048576,
            'path': '/dev/sda1',
            'encrypted_provider': None
        },
        {
            'name': 'sda2',
            'partition_type': 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b',
            'partition_uuid': 'd83226a3-246f-4242-9468-d8deb08ea3d6',
            'disk': 'sda',
            'size': 536870912,
            'path': '/dev/sda2',
            'encrypted_provider': None
        },
        {
            'name': 'sda3',
            'partition_type': '6a898cc3-1dd2-11b2-99a6-080020736631',
            'partition_uuid': '89cf93fd-a5a8-4106-8d4e-eec800124bcd',
            'disk': 'sda',
            'size': 46704606720,
            'path': '/dev/sda3',
            'encrypted_provider': None
        },
        {
            'name': 'sda4',
            'partition_type': '0657fd6d-a4ab-43c4-84e5-0933c84b4f4f',
            'partition_uuid': 'cca6903c-0ded-475d-a622-98855d32437e',
            'disk': 'sda',
            'size': 17179869184,
            'path': '/dev/sda4',
            'encrypted_provider': None
        }
    ],
    'sdb': [
        {
            'name': 'sdb1',
            'partition_type': '0657fd6d-a4ab-43c4-84e5-0933c84b4f4f',
            'partition_uuid': '8c1d813e-c1ae-4f80-b15d-dd57375266bc',
            'disk': 'sdb',
            'size': 2147484160,
            'path': '/dev/sdb1',
            'encrypted_provider': None
        },
        {
            'name': 'sdb2',
            'partition_type': '6a898cc3-1dd2-11b2-99a6-080020736631',
            'partition_uuid': '41adc2c8-8b87-4e93-9e01-539a544d1c00',
            'disk': 'sdb',
            'size': 19324207104,
            'path': '/dev/sdb2',
            'encrypted_provider': None
        }
    ],
    'sdc': [
        {
            'name': 'sdc1',
            'partition_type': '0657fd6d-a4ab-43c4-84e5-0933c84b4f4f',
            'partition_uuid': '22227899-09b0-4019-b439-31b1481aad53',
            'disk': 'sdc',
            'size': 2147484160,
            'path': '/dev/sdc1',
            'encrypted_provider': None
        },
        {
            'name': 'sdc2',
            'partition_type': '6a898cc3-1dd2-11b2-99a6-080020736631',
            'partition_number': 2,
            'partition_uuid': '40fa5413-e654-4570-b71b-d8f6657fbc96',
            'disk': 'sdc',
            'size': 19324207104,
            'path': '/dev/sdc2',
            'encrypted_provider': None
        }
    ],
    'sdd': [
        {
            'name': 'sdd1',
            'partition_type': '21686148-6449-6e6f-744e-656564454649',
            'partition_uuid': 'ee6e4763-1e61-466d-9972-e3c46dfc4a1c',
            'disk': 'sda',
            'size': 1048576,
            'path': '/dev/sda1',
            'encrypted_provider': None
        },
        {
            'name': 'sdd2',
            'partition_type': 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b',
            'partition_uuid': 'd83226a3-246f-4242-9468-d8deb08ea3d6',
            'disk': 'sda',
            'size': 536870912,
            'path': '/dev/sda2',
            'encrypted_provider': None
        },
        {
            'name': 'sdd3',
            'partition_type': '6a898cc3-1dd2-11b2-99a6-080020736631',
            'partition_uuid': '89cf93fd-a5a8-4106-8d4e-eec800124bcd',
            'disk': 'sda',
            'size': 46704606720,
            'path': '/dev/sda3',
            'encrypted_provider': None
        },
        {
            'name': 'sdd4',
            'partition_type': '0657fd6d-a4ab-43c4-84e5-0933c84b4f4f',
            'partition_uuid': 'cca6903c-0ded-475d-a622-98855d32437e',
            'disk': 'sda',
            'size': 17179869184,
            'path': '/dev/sda4',
            'encrypted_provider': None
        },
    ],
    'sde': [
        {
            'name': 'sde1',
            'partition_type': '0657fd6d-a4ab-43c4-84e5-0933c84b4f4f',
            'partition_uuid': '8c1d813e-c1ae-4f80-b15d-dd57375266bc',
            'disk': 'sde',
            'size': 2147484160,
            'path': '/dev/sde1',
            'encrypted_provider': None
        },
        {
            'name': 'sde2',
            'partition_type': '6a898cc3-1dd2-11b2-99a6-080020736632',
            'partition_uuid': '41adc2c8-8b87-4e93-9e01-539a544d1c00',
            'disk': 'sde',
            'size': 19324207104,
            'path': '/dev/sde2',
            'encrypted_provider': None
        }
    ],
    'sdf': [
        {
            'name': 'sdf1',
            'partition_type': '0657fd6d-a4ab-43c4-84e5-0933c84b4f4f',
            'partition_uuid': '22227899-09b0-4019-b439-31b1481aad53',
            'disk': 'sdf',
            'size': 2147484160,
            'path': '/dev/sdf1',
            'encrypted_provider': None
        },
        {
            'name': 'sdf2',
            'partition_type': '6a898cc3-1dd2-11b2-99a6-080020736631',
            'partition_number': 2,
            'partition_uuid': '40fa5413-e654-4570-b71b-d8f6657fbc96',
            'disk': 'sdf',
            'size': 19324207104,
            'path': '/dev/sdf2',
            'encrypted_provider': None
        }
    ],
    'sdg': [
        {
            'name': 'sdg2',
            'partition_type': '6a898cc3-1dd2-11b2-99a6-080020736631',
            'partition_number': 2,
            'partition_uuid': '40fa5413-e654-4570-b71b-d8f6657fbc96',
            'disk': 'sdg',
            'size': 19324207104,
            'path': '/dev/sdf2',
            'encrypted_provider': None
        }
    ]
}


@pytest.mark.parametrize('pool_disks,boot_disk,expected_output', [
    (['sdb', 'sdc'], ['sda'], ['/dev/mapper/sda4']),  # A mirror with a boot swap partition
    (['sdb', 'sdc'], ['sdg'], ['/dev/mapper/swap0']),  # A mirror without  any boot swap partition
    (['sdb', 'sdc', 'sde', 'sdf'], ['sdg'], ['/dev/mapper/swap0', '/dev/mapper/swap1']),  # Two mirrors
    ([], ['sda', 'sdd'], ['/dev/mapper/swap0']),  # A boot mirror
    (['sdb', 'sdc', 'sde', 'sdf'], ['sda', 'sdd'], ['/dev/mapper/swap0']),  # Boot mirror
    (['sdf'], ['sdg'], ['/dev/mapper/sdf1']),  # Single swap partition
    (['sdf', 'sda'], ['sdg'], ['/dev/mapper/sdf1']),  # Swap partitions with different sizes
])
@pytest.mark.asyncio
async def test_swap_partition_configuration(pool_disks, boot_disk, expected_output):
    m = Middleware()
    m['disk.swap_redundancy'] = AsyncMock(return_value=2)
    m['system.is_ha_capable'] = AsyncMock(return_value=False)
    m['pool.get_disks'] = AsyncMock(return_value=pool_disks)
    m['boot.get_disks'] = AsyncMock(return_value=boot_disk)
    m['disk.get_swap_mirrors'] = AsyncMock(return_value=[])
    m['disk.list_partitions'] = lambda disk: ALL_PARTITIONS[disk]
    m['disk.remove_degraded_mirrors'] = AsyncMock(return_value=None)
    m['disk.get_swap_devices'] = AsyncMock(return_value=[])
    m['disk.get_valid_swap_partition_type_uuids'] = AsyncMock(return_value=['0657fd6d-a4ab-43c4-84e5-0933c84b4f4f'])
    m['disk.swaps_remove_disks_unlocked'] = AsyncMock(return_value=None)
    m['disk.create_swap_mirror'] = AsyncMock(return_value=None)
    with patch('middlewared.plugins.disk_.swap_configure.run') as run:
        run.return_value = Mock(returncode=0)
        with patch('os.path.realpath', side_effect=expected_output):
            assert (await DiskService(m).swaps_configure()) == expected_output
