import json

import pytest
from pytest_dependency import depends

from middlewared.test.integration.utils import call, ssh

DISKS = list(call('device.get_disks').keys())
CONTROL = None


@pytest.mark.dependency(name='GET_DISK_INFO')
def test_get_disk_info():
    global CONTROL
    CONTROL = {i['name']: i for i in json.loads(ssh('lsblk -bJ -o NAME,SIZE'))['blockdevices']}


@pytest.mark.parametrize('disk', DISKS)
def test_get_dev_size_for(disk, request):
    depends(request, ['GET_DISK_INFO'])
    assert CONTROL[disk]['size'] == call('disk.get_dev_size', disk)
