import pytest
from middlewared.test.integration.utils import call, ssh

pytestmark = pytest.mark.disk


def test_device_get_disks_size():
    boot_disk = call('boot.get_disks')[0]
    fdisk_size = int(ssh(f'fdisk -s /dev/{boot_disk}').strip()) * 1024
    assert call('device.get_disks')[boot_disk]['size'] == fdisk_size
