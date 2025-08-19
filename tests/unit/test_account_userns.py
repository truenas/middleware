import pytest

from contextlib import contextmanager
from truenas_api_client import Client, ClientException


@contextmanager
def create_group(name, **kwargs):
    with Client() as c:
        pk = c.call('group.create', {'name': name} | kwargs)
        grp = c.call('group.query', [['id', '=', pk]], {'get': True})

        try:
            yield grp
        finally:
            c.call('group.delete', pk)


@contextmanager
def create_user(name, **kwargs):
    with Client() as c:
        usr = c.call('user.create', {
            'username': name,
            'full_name': name,
            'random_password': True,
            'group_create': True
        } | kwargs)
        try:
            yield usr

        finally:
            c.call('user.delete', usr['id'])


@contextmanager
def do_idmap(account_type, data):
    with Client() as c:
        c.call(f'{account_type}.update', data['id'], {'userns_idmap': 'DIRECT'})
        try:
            yield data
        finally:
            c.call(f'{account_type}.update', data['id'], {'userns_idmap': None})


@pytest.fixture(scope='module')
def group():
    with create_group('userns_test_grp') as grp:
        yield grp


@pytest.fixture(scope='function')
def privileged_group(group):
    with Client() as c:
        priv = c.call('privilege.create', {
            'name': 'PRIV',
            'local_groups': [group['gid']],
            'roles': ['READONLY_ADMIN'],
            'web_shell': False
        })
        try:
            yield (priv, group)
        finally:
            c.call('privilege.delete', priv['id'])


@pytest.fixture(scope='function')
def user():
    with create_user('userns_test_usr') as usr:
        yield usr


@pytest.fixture(scope='function')
def privileged_user(user, privileged_group):
    with Client() as c:
        yield c.call('user.update', user['id'], {'groups': user['groups'] + [privileged_group[1]['id']]})


def test__privileged_user_idmap_namespace_deny(privileged_user):
    with pytest.raises(ClientException, match='privileged account'):
        with Client() as c:
            assert privileged_user['roles'] != []
            c.call('user.update', privileged_user['id'], {'userns_idmap': 'DIRECT'})


def test__privileged_group_idmap_namespace_deny(privileged_group):
    with pytest.raises(ClientException, match='privileged account'):
        with Client() as c:
            c.call('group.update', privileged_group[1]['id'], {'userns_idmap': 'DIRECT'})


def test__builtin_user_idmap_namespace_deny():
    with pytest.raises(ClientException, match='This attribute cannot be changed'):
        with Client() as c:
            pk = c.call('user.query', [['uid', '=', 666]], {'get': True})['id']
            c.call('user.update', pk, {'userns_idmap': 'DIRECT'})


def test__builtin_group_idmap_namespace_deny():
    with pytest.raises(ClientException, match='User namespace idmaps may not be configured for builtin accounts.'):
        with Client() as c:
            pk = c.call('group.query', [['gid', '=', 666]], {'get': True})['id']
            c.call('group.update', pk, {'userns_idmap': 'DIRECT'})


def test__create_privilege_with_idmap_group_deny(group):
    with do_idmap('group', group):
        with pytest.raises(ClientException, match='user namespace idmap configured.'):
            with Client() as c:
                c.call('privilege.create', {
                    'name': 'PRIV',
                    'local_groups': [group['gid']],
                    'roles': ['READONLY_ADMIN'],
                    'web_shell': False
                })


def test__update_privilege_with_idmap_group_deny(group):
    with do_idmap('group', group):
        with Client() as c:
            priv = c.call('privilege.create', {
                'name': 'PRIV',
                'local_groups': [666],
                'roles': ['READONLY_ADMIN'],
                'web_shell': False
            })

            try:
                with pytest.raises(ClientException, match='user namespace idmap configured.'):
                    c.call('privilege.update', priv['id'], {'local_groups': [group['gid']]})
            finally:
                c.call('privilege.delete', priv['id'])
