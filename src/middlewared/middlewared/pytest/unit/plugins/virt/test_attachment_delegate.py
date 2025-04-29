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
                'id': 'test-instance',
                'name': 'test-instance',
                'disk_devices': [
                    'disk0'
                ],
                'dataset': 'test4'
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
                'id': 'test-instance',
                'name': 'test-instance',
                'disk_devices': [
                    'disk1'
                ],
                'dataset': 'test/test_zvol'
            }
        ],
    ),
    (
        '/mnt/test',
        [
            {
                'name': 'disk0',
                'dev_type': 'DISK',
                'source': '/mnt/evo/test_zvol',
                'storage_pool': 'test2'
            },
            {
                'name': 'disk1',
                'dev_type': 'DISK',
                'source': '/mnt/test/test_zvol',
                'storage_pool': 'test2'
            },
        ],
        [
            {
                'id': 'test-instance',
                'name': 'test-instance',
                'disk_devices': [
                    'disk1'
                ],
                'dataset': 'test'
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
                'id': 'test-instance',
                'name': 'test-instance',
                'disk_devices': [
                    'disk0'
                ],
                'dataset': 'test45'
            }
        ],
    ),
    (
        '/mnt/test2',
        [
            {
                'name': 'disk0',
                'dev_type': 'DISK',
                'source': '/mnt/evo/test_zvol',
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
                'id': 'test-instance',
                'name': 'test-instance',
                'disk_devices': [],
                'dataset': 'test2'
            }
        ],
    ),
    (
        '/mnt/test3',
        [
            {
                'name': 'disk0',
                'dev_type': 'DISK',
                'source': '/mnt/evo/test_zvol',
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
                'id': 'test-instance',
                'name': 'test-instance',
                'disk_devices': ['disk0', 'disk1'],
                'dataset': 'test3'
            }
        ],
    ),
])
@pytest.mark.asyncio
async def test_virt_instance_attachment_delegate(path, devices, expected):
    m = Middleware()
    m['virt.instance.query'] = lambda *arg: INSTANCE_QUERY
    m['virt.instance.device_list'] = lambda *arg: devices
    m['filesystem.is_child'] = is_child_realpath
    assert await VirtFSAttachmentDelegate(m).query(path, False) == expected
