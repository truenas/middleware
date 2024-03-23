import pytest
from middlewared.test.integration.utils import call

pytestmark = pytest.mark.disk


def test_device_get_disk_names():
    assert set(list(call('device.get_disks', False, True))) == set(call('device.get_disk_names'))
