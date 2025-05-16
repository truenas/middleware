import pytest

from auto_config import pool_name
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import ssh


@pytest.fixture(scope='module')
def unprivileged_user():
    with user({
        'username': 'unprivileged',
        'full_name': 'Unprivileged',
        'password': 'password',
        'group_create': True,
        'home': f'/mnt/{pool_name}',
        'ssh_password_enabled': True,
    }) as u:
        yield u


@pytest.mark.parametrize('shell', ['/usr/bin/bash', '/usr/bin/zsh'])
def test_unprivileged_user_has_access_to_sbin_zfs(unprivileged_user, shell):
    ssh(f'{shell} -c "zpool status"', user='unprivileged', password='password')
