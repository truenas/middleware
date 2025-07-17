import pytest
from truenas_api_client import Client, ClientException


@pytest.fixture(scope='module')
def local_user():
    with Client() as c:
        usr = c.call('user.create', {
            'username': 'test_local_user',
            'full_name': 'test_local_user',
            'random_password': True,
            'group_create': True
        })
        try:
            yield usr

        finally:
            c.call('user.delete', usr['id'])


@pytest.fixture(scope='module')
def incus_admin_dbid():
    with Client() as c:
        yield c.call('group.query', [['name', '=', 'incus-admin']], {'get': True})['id']


@pytest.fixture(scope='module')
def builtin_admins_dbid():
    with Client() as c:
        yield c.call('group.query', [['name', '=', 'builtin_administrators']], {'get': True})['id']


@pytest.mark.parametrize('key,value', (
    ('name', 'canary'),
    ('smb', True),
    ('sudo_commands', ['/usr/sbin/zpool']),
    ('sudo_commands_nopasswd', ['/usr/sbin/zpool']),
))
def test__builtin_group_immutable(key, value, incus_admin_dbid):
    with pytest.raises(ClientException, match='Immutable groups cannot be changed'):
        with Client() as c:
            c.call('group.update', incus_admin_dbid, {key: value})


def test__builtin_group_deny_member_change(incus_admin_dbid, local_user):
    with pytest.raises(ClientException, match='Immutable groups cannot be changed'):
        with Client() as c:
            c.call('group.update', incus_admin_dbid, {'users': [local_user['id']]})


def test__change_full_admin_member(local_user, builtin_admins_dbid):
    with Client() as c:
        c.call('group.update', builtin_admins_dbid, {'users': [1, local_user['id']]})
