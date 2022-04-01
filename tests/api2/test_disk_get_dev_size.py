import json

import pytest
from pytest_dependency import depends

from middlewared.test.integration.utils import call, ssh
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


@pytest.mark.dependency(name='GET_DISK_INFO')
def test_get_disk_info():
    global CONTROL
    CONTROL = {i['name']: i for i in json.loads(ssh('lsblk -bJ -o NAME,SIZE'))['blockdevices']}


def test_get_dev_size_for_all_disks(request):
    depends(request, ['GET_DISK_INFO'])
    for disk, disk_info in CONTROL.items():
        assert disk_info['size'] == call('disk.get_dev_size', disk)
