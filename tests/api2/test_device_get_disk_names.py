from middlewared.test.integration.utils import call


def test_device_get_disk_names():
    assert set(list(call('device.get_disks', False, True))) == set(call('device.get_disk_names'))
