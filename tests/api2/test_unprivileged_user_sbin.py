import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import ssh


@pytest.fixture(scope='module')
def unprivileged_user():
    with user({
        'username': 'unprivileged',
        'full_name': 'Unprivileged',
        'password': 'password',
        'group_create': True,
        'ssh_password_enabled': True,
        'shell': '/usr/bin/sh',
    }) as u:
        yield u


@pytest.mark.parametrize('shell', ['/usr/bin/bash', '/usr/bin/dash', '/usr/bin/sh', '/usr/bin/zsh'])
def test_unprivileged_user_has_access_to_sbin_zfs(unprivileged_user, shell):
    ssh(f'{shell} -l -c "zpool status"', user='unprivileged', password='password')
