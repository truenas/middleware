import contextlib

import pytest

from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.assets.pool import another_pool

import os
import sys
sys.path.append(os.getcwd())

UNUSED_DISKS = call('disk.get_unused')
pytestmark = pytest.mark.skipif(not bool(UNUSED_DISKS), reason='Skipping for test disk is not available for this test')
POOL_NAME = 'test_pool_with_lvm_volumes'
TEST_DISK = UNUSED_DISKS[0]['name']
GROUP_NAME = 'test_group1'
LVM_NAME = 'lv01'


@contextlib.contextmanager
def pv_disks(disks_path):
    try:
        ssh(f'pvcreate {" ".join(disks_path)}', check=False)
        yield
    finally:
        ssh(f'pvremove {" ".join(disks_path)}', check=False)


@contextlib.contextmanager
def disk_volume_groups(group_name, disks):
    try:
        ssh(f'vgcreate {group_name} {" ".join(disks)}', check=False)
        yield
    finally:
        ssh(f'vgremove {os.path.join("/dev", group_name)}', check=False)


@contextlib.contextmanager
def lvm_disk(group_name, size, lv_name):
    try:
        ssh(f'lvcreate -L {size} -n {lv_name} {group_name}', check=False)
        yield
    finally:
        ssh(f'lvremove {os.path.join("/dev", group_name, lv_name)}', check=False)


@contextlib.contextmanager
def disk_with_lvm(disk):
    call('disk.wipe', disk, 'QUICK')
    disk_path = os.path.join('/dev', disk)
    with pv_disks([disk_path]):
        with disk_volume_groups(GROUP_NAME, [disk_path]):
            with lvm_disk(GROUP_NAME, '1G', LVM_NAME):
                yield


def test_remove_lvm_from_disk():
    with disk_with_lvm(TEST_DISK):
        assert call('device.list_lvm_to_disk_mapping') == {TEST_DISK: [[GROUP_NAME, LVM_NAME]]}
        assert call('disk.remove_lvm_from_disks', [TEST_DISK]) is None
        assert call('device.list_lvm_to_disk_mapping') == {}


def test_lvm_disks_pool_creation():
    with disk_with_lvm(TEST_DISK):
        with another_pool({
            'name': POOL_NAME,
            'encryption': False,
            'topology': {'data': [{
                'type': 'STRIPE', 'disks': [TEST_DISK]
            }]}
        }) as pool:
            assert pool['name'] == POOL_NAME
            assert call('device.list_lvm_to_disk_mapping') == {}
