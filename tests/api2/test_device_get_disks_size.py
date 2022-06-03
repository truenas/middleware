import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

import pytest

from middlewared.test.integration.utils import call, ssh
from auto_config import dev_test

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


def test_device_get_disks_size():
    boot_disk = call('boot.get_disks')[0]
    fdisk_size = int(ssh('fdisk -s /dev/{boot_disk}').strip()) * 1024
    assert call('device.get_disks')[boot_disk]['size'] == fdisk_size
