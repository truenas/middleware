import json

import pytest

from middlewared.test.integration.utils import call, ssh

DISKS = list(call('device.get_disks').keys())
CONTROL = {i['name']: i for i in json.loads(ssh('lsblk -bJ -o NAME,SIZE'))['blockdevices']}

@pytest.mark.parametrize('disk', DISKS)
def test_get_dev_size_for(disk):
    assert CONTROL[disk]['size'] == call('disk.get_dev_size', disk)
