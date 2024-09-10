import os

import pytest

from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh


POOL_NAME = 'test_format_pool'
ZFS_PART_UUID = '6a898cc3-1dd2-11b2-99a6-080020736631'


def get_disk_uuid_mapping(unused_disks):
    disk_uuid = {}
    for disk in filter(
        lambda n: n['name'] in unused_disks and n['parts'], call('device.get_disks', True, False).values()
    ):
        if partition := next((part for part in disk['parts'] if part['partition_type'] == ZFS_PART_UUID), None):
            disk_uuid[disk['name']] = os.path.join('/dev/disk/by-partuuid', partition['partition_uuid'])

    return disk_uuid


def get_pool_status(unused_disks, real_paths=False, replaced=False):
    disk_uuid_mapping = get_disk_uuid_mapping(unused_disks)
    return {
        'disks': {
            f'{disk_uuid_mapping[unused_disks[4]] if not real_paths else unused_disks[4]}': {
                'pool_name': POOL_NAME,
                'disk_status': 'AVAIL' if not replaced else 'ONLINE',
                'disk_read_errors': 0,
                'disk_write_errors': 0,
                'disk_checksum_errors': 0,
                'vdev_name': 'stripe' if not replaced else 'spare-0',
                'vdev_type': 'spares' if not replaced else 'data',
                'vdev_disks': [
                    f'{disk_uuid_mapping[unused_disks[4]] if not real_paths else unused_disks[4]}'
                ] if not replaced else [
                    f'{disk_uuid_mapping[unused_disks[1]] if not real_paths else unused_disks[1]}',
                    f'{disk_uuid_mapping[unused_disks[4]] if not real_paths else unused_disks[4]}'
                ]
            },
            f'{disk_uuid_mapping[unused_disks[3]] if not real_paths else unused_disks[3]}': {
                'pool_name': POOL_NAME,
                'disk_status': 'ONLINE',
                'disk_read_errors': 0,
                'disk_write_errors': 0,
                'disk_checksum_errors': 0,
                'vdev_name': 'stripe',
                'vdev_type': 'logs',
                'vdev_disks': [
                    f'{disk_uuid_mapping[unused_disks[3]] if not real_paths else unused_disks[3]}'
                ]
            },
            f'{disk_uuid_mapping[unused_disks[2]] if not real_paths else unused_disks[2]}': {
                'pool_name': POOL_NAME,
                'disk_status': 'ONLINE',
                'disk_read_errors': 0,
                'disk_write_errors': 0,
                'disk_checksum_errors': 0,
                'vdev_name': 'stripe',
                'vdev_type': 'dedup',
                'vdev_disks': [
                    f'{disk_uuid_mapping[unused_disks[2]] if not real_paths else unused_disks[2]}'
                ]
            },
            f'{disk_uuid_mapping[unused_disks[5]] if not real_paths else unused_disks[5]}': {
                'pool_name': POOL_NAME,
                'disk_status': 'ONLINE',
                'disk_read_errors': 0,
                'disk_write_errors': 0,
                'disk_checksum_errors': 0,
                'vdev_name': 'stripe',
                'vdev_type': 'special',
                'vdev_disks': [
                    f'{disk_uuid_mapping[unused_disks[5]] if not real_paths else unused_disks[5]}'
                ]
            },
            f'{disk_uuid_mapping[unused_disks[0]] if not real_paths else unused_disks[0]}': {
                'pool_name': POOL_NAME,
                'disk_status': 'ONLINE',
                'disk_read_errors': 0,
                'disk_write_errors': 0,
                'disk_checksum_errors': 0,
                'vdev_name': 'stripe',
                'vdev_type': 'l2cache',
                'vdev_disks': [
                    f'{disk_uuid_mapping[unused_disks[0]] if not real_paths else unused_disks[0]}'
                ]
            },
            f'{disk_uuid_mapping[unused_disks[1]] if not real_paths else unused_disks[1]}': {
                'pool_name': POOL_NAME,
                'disk_status': 'ONLINE',
                'disk_read_errors': 0,
                'disk_write_errors': 0,
                'disk_checksum_errors': 0,
                'vdev_name': 'stripe' if not replaced else 'spare-0',
                'vdev_type': 'data',
                'vdev_disks': [
                    f'{disk_uuid_mapping[unused_disks[1]] if not real_paths else unused_disks[1]}'
                ] if not replaced else [
                    f'{disk_uuid_mapping[unused_disks[1]] if not real_paths else unused_disks[1]}',
                    f'{disk_uuid_mapping[unused_disks[4]] if not real_paths else unused_disks[4]}'
                ]
            }
        },
        POOL_NAME: {
            'spares': {
                f'{disk_uuid_mapping[unused_disks[4]] if not real_paths else unused_disks[4]}': {
                    'pool_name': POOL_NAME,
                    'disk_status': 'AVAIL' if not replaced else 'INUSE',
                    'disk_read_errors': 0,
                    'disk_write_errors': 0,
                    'disk_checksum_errors': 0,
                    'vdev_name': 'stripe',
                    'vdev_type': 'spares',
                    'vdev_disks': [
                        f'{disk_uuid_mapping[unused_disks[4]] if not real_paths else unused_disks[4]}'
                    ]
                }
            },
            'logs': {
                f'{disk_uuid_mapping[unused_disks[3]] if not real_paths else unused_disks[3]}': {
                    'pool_name': POOL_NAME,
                    'disk_status': 'ONLINE',
                    'disk_read_errors': 0,
                    'disk_write_errors': 0,
                    'disk_checksum_errors': 0,
                    'vdev_name': 'stripe',
                    'vdev_type': 'logs',
                    'vdev_disks': [
                        f'{disk_uuid_mapping[unused_disks[3]] if not real_paths else unused_disks[3]}'
                    ]
                }
            },
            'dedup': {
                f'{disk_uuid_mapping[unused_disks[2]] if not real_paths else unused_disks[2]}': {
                    'pool_name': POOL_NAME,
                    'disk_status': 'ONLINE',
                    'disk_read_errors': 0,
                    'disk_write_errors': 0,
                    'disk_checksum_errors': 0,
                    'vdev_name': 'stripe',
                    'vdev_type': 'dedup',
                    'vdev_disks': [
                        f'{disk_uuid_mapping[unused_disks[2]] if not real_paths else unused_disks[2]}'
                    ]
                }
            },
            'special': {
                f'{disk_uuid_mapping[unused_disks[5]] if not real_paths else unused_disks[5]}': {
                    'pool_name': POOL_NAME,
                    'disk_status': 'ONLINE',
                    'disk_read_errors': 0,
                    'disk_write_errors': 0,
                    'disk_checksum_errors': 0,
                    'vdev_name': 'stripe',
                    'vdev_type': 'special',
                    'vdev_disks': [
                        f'{disk_uuid_mapping[unused_disks[5]] if not real_paths else unused_disks[5]}'
                    ]
                }
            },
            'l2cache': {
                f'{disk_uuid_mapping[unused_disks[0]] if not real_paths else unused_disks[0]}': {
                    'pool_name': POOL_NAME,
                    'disk_status': 'ONLINE',
                    'disk_read_errors': 0,
                    'disk_write_errors': 0,
                    'disk_checksum_errors': 0,
                    'vdev_name': 'stripe',
                    'vdev_type': 'l2cache',
                    'vdev_disks': [
                        f'{disk_uuid_mapping[unused_disks[0]] if not real_paths else unused_disks[0]}'
                    ]
                }
            },
            'data': {
                f'{disk_uuid_mapping[unused_disks[1]] if not real_paths else unused_disks[1]}': {
                    'pool_name': POOL_NAME,
                    'disk_status': 'ONLINE',
                    'disk_read_errors': 0,
                    'disk_write_errors': 0,
                    'disk_checksum_errors': 0,
                    'vdev_name': 'stripe',
                    'vdev_type': 'data',
                    'vdev_disks': [
                        f'{disk_uuid_mapping[unused_disks[1]] if not real_paths else unused_disks[1]}'
                    ]
                }
            } if not replaced else {
                f'{disk_uuid_mapping[unused_disks[1]] if not real_paths else unused_disks[1]}': {
                    'pool_name': POOL_NAME,
                    'disk_status': 'ONLINE',
                    'disk_read_errors': 0,
                    'disk_write_errors': 0,
                    'disk_checksum_errors': 0,
                    'vdev_name': 'spare-0',
                    'vdev_type': 'data',
                    'vdev_disks': [
                        f'{disk_uuid_mapping[unused_disks[1]] if not real_paths else unused_disks[1]}',
                        f'{disk_uuid_mapping[unused_disks[4]] if not real_paths else unused_disks[4]}'
                    ]
                },
                f'{disk_uuid_mapping[unused_disks[4]] if not real_paths else unused_disks[4]}': {
                    'pool_name': POOL_NAME,
                    'disk_status': 'ONLINE',
                    'disk_read_errors': 0,
                    'disk_write_errors': 0,
                    'disk_checksum_errors': 0,
                    'vdev_name': 'spare-0',
                    'vdev_type': 'data',
                    'vdev_disks':  [
                        f'{disk_uuid_mapping[unused_disks[1]] if not real_paths else unused_disks[1]}',
                        f'{disk_uuid_mapping[unused_disks[4]] if not real_paths else unused_disks[4]}'
                    ]
                },
            }
        }
    }


@pytest.fixture(scope='module')
def test_pool():
    unused_disks = call('disk.get_unused')
    if len(unused_disks) < 7:
        pytest.skip('Insufficient number of disks to perform these tests')

    with another_pool({
        'name': POOL_NAME,
        'topology': {
            'cache': [{'type': 'STRIPE', 'disks': [unused_disks[0]['name']]}],
            'data': [{'type': 'STRIPE', 'disks': [unused_disks[1]['name']]}],
            'dedup': [{'type': 'STRIPE', 'disks': [unused_disks[2]['name']]}],
            'log': [{'type': 'STRIPE', 'disks': [unused_disks[3]['name']]}],
            'spares': [unused_disks[4]['name']],
            'special': [{'type': 'STRIPE', 'disks': [unused_disks[5]['name']]}]
        },
        'allow_duplicate_serials': True,
    }) as pool_info:
        yield pool_info, unused_disks


@pytest.mark.parametrize('real_path', [True, False])
def test_zpool_status_format(test_pool, real_path):
    assert call('zpool.status', {'name': POOL_NAME, 'real_paths': real_path}) == get_pool_status(
        [disk['name'] for disk in test_pool[1]], real_path
    )


def test_replaced_disk_zpool_status_format(test_pool):
    disk_mapping = get_disk_uuid_mapping([disk['name'] for disk in test_pool[1]])
    data_disk = test_pool[1][1]['name']
    spare_disk = test_pool[1][4]['name']
    ssh(
        f'zpool replace '
        f'{test_pool[0]["name"]} '
        f'{os.path.basename(disk_mapping[data_disk])} '
        f'{os.path.basename(disk_mapping[spare_disk])}',
    )
    for real_path in (True, False):
        assert call(
            'zpool.status', {"name": POOL_NAME, "real_paths": real_path}
        ) == get_pool_status(
            [disk['name'] for disk in test_pool[1]], real_path, True
        )
