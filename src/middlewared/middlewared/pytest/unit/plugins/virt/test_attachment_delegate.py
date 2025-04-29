import pytest

from middlewared.pytest.unit.middleware import Middleware
from middlewared.plugins.virt.attachments import VirtFSAttachmentDelegate
from middlewared.utils.path import is_child_realpath


INSTANCE_QUERY = [
    {
        'id': 'test-instance',
        'name': 'test-instance',
        'storage_pool': 'test2'
    },
]

GLOBAL_CONFIG = {
    'pool': 'test',
    'storage_pools': [
        'test',
        'test1',
        'test2',
        'test3',
        'test4',
    ],
}


@pytest.mark.parametrize('path,devices,expected', [
    (
        '/mnt/test4',
        [
            {
                'name': 'disk0',
                'dev_type': 'DISK',
                'source': '/dev/zvol/test4/test_zvol',
                'storage_pool': 'test2'
            },
            {
                'name': 'disk1',
                'dev_type': 'DISK',
                'source': '/dev/zvol/test/test_zvol',
                'storage_pool': 'test2'
            },
            {
                'name': 'eth0',
                'dev_type': 'NIC',
            },
        ],
        [
            {
                'id': 'test4',
                'name': 'virt',
                'instances': [
                    {
                        'id': 'test-instance',
                        'name': 'test-instance',
                        'disk_devices': ['disk0'],
                        'dataset': 'test4'
                    }
                ],
                'incus_pool_change': True
            }
        ],
    ),
    (
        '/mnt/test/test_zvol',
        [
            {
                'name': 'disk0',
                'dev_type': 'DISK',
                'source': '/dev/zvol/test2/test_zvol',
                'storage_pool': 'test2'
            },
            {
                'name': 'disk1',
                'dev_type': 'DISK',
                'source': '/dev/zvol/test/test_zvol',
                'storage_pool': 'test2'
            },
        ],
        [
            {
                'id': 'test/test_zvol',
                'name': 'virt',
                'instances': [
                    {
                        'id': 'test-instance',
                        'name': 'test-instance',
                        'disk_devices': ['disk1'],
                        'dataset': 'test/test_zvol'
                    }
                ],
                'incus_pool_change': False
            }
        ],
    ),
    (
        '/mnt/test5',
        [
            {
                'name': 'disk0',
                'dev_type': 'DISK',
                'source': '/mnt/test5/test_zvol',
                'storage_pool': 'test2'
            },
            {
                'name': 'disk1',
                'dev_type': 'DISK',
                'source': '/mnt/test5/test_zvol',
                'storage_pool': 'test2'
            },
        ],
        [
            {
                'id': 'test5',
                'name': 'virt',
                'instances': [
                    {
                        'id': 'test-instance',
                        'name': 'test-instance',
                        'disk_devices': ['disk0', 'disk1'],
                        'dataset': 'test5'
                    }
                ],
                'incus_pool_change': False
            }
        ],
    ),
    (
        '/mnt/test45',
        [
            {
                'name': 'disk0',
                'dev_type': 'DISK',
                'source': '/mnt/test45',
                'storage_pool': 'test2'
            },
        ],
        [
            {
                'id': 'test45',
                'name': 'virt',
                'instances': [
                    {
                        'id': 'test-instance',
                        'name': 'test-instance',
                        'disk_devices': ['disk0'],
                        'dataset': 'test45'
                    }
                ],
                'incus_pool_change': False
            }
        ]
    ),
    (
        '/mnt/test2',
        [
            {
                'name': 'disk0',
                'dev_type': 'DISK',
                'source': '/mnt/test4/test_zvol',
                'storage_pool': 'test3'
            },
            {
                'name': 'disk1',
                'dev_type': 'DISK',
                'source': '/mnt/test/test_zvol',
                'storage_pool': 'test3'
            }
        ],
        [
            {
                'id': 'test2',
                'name': 'virt',
                'instances': [
                    {
                        'id': 'test-instance',
                        'name': 'test-instance',
                        'disk_devices': [],
                        'dataset': 'test2'
                    }
                ],
                'incus_pool_change': True
            }
        ],
    ),
    (
        '/mnt/test',
        [
            {
                'name': 'disk0',
                'dev_type': 'DISK',
                'source': '/mnt/test4/test_zvol',
                'storage_pool': 'test3'
            },
            {
                'name': 'disk1',
                'dev_type': 'DISK',
                'source': '/mnt/test/test_zvol',
                'storage_pool': 'test3'
            }
        ],
        [
            {
                'id': 'test',
                'name': 'virt',
                'instances': [
                    {
                        'id': 'test-instance',
                        'name': 'test-instance',
                        'disk_devices': ['disk1'],
                        'dataset': 'test'
                    }
                ],
                'incus_pool_change': True
            }
        ],
    ),
])
@pytest.mark.asyncio
async def test_virt_instance_attachment_delegate(path, devices, expected):
    m = Middleware()
    m['virt.global.config'] = lambda *arg: GLOBAL_CONFIG
    m['virt.instance.query'] = lambda *arg: INSTANCE_QUERY
    m['virt.instance.device_list'] = lambda *arg: devices
    m['filesystem.is_child'] = is_child_realpath
    assert await VirtFSAttachmentDelegate(m).query(path, False) == expected
