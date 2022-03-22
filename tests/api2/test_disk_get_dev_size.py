import pytest

from middlewared.test.integration.utils import call

DISKS = list(call('device.get_disks').keys())
TYPES = (type(None), int)


@pytest.mark.parametrize('disk', DISKS)
def test_get_dev_size_for(disk):
    assert isinstance(call('disk.get_dev_size', disk), TYPES)
