import pytest

from auto_config import pool_name
from middlewared.test.integration.utils.call import call
from middlewared.test.integration.utils.ssh import ssh

pytestmark = pytest.mark.skip('Disable VIRT tests for the moment')


def test_virt_pool():
    call('virt.global.update', {'pool': pool_name}, job=True)
    ssh(f'zfs list {pool_name}/.ix-virt')


def test_virt_no_pool():
    call('virt.global.update', {'pool': None}, job=True)
    ssh('incus storage show default 2>&1 | grep "incus daemon doesn\'t appear to be started"')


def test_virt_pool_auto_bridge():
    call('virt.global.update', {'pool': pool_name, 'bridge': None}, job=True)
    ssh('ifconfig incusbr0')
