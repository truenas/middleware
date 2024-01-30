import json

import pytest

from middlewared.test.integration.utils import call, ssh

pytestmark = pytest.mark.disk


@pytest.fixture(scope="session")
def blockdevices():
    return {i['name']: i for i in json.loads(ssh('lsblk -bJ -o NAME,SIZE'))['blockdevices']}


def test_get_dev_size_for_all_disks(blockdevices):
    for disk, disk_info in blockdevices.items():
        assert disk_info['size'] == call('disk.get_dev_size', disk)
