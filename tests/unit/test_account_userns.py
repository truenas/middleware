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


def test__user_duplicate_explicit_idmap_deny():
    with create_user('idmap_dup_a') as u1, create_user('idmap_dup_b') as u2:
        with Client() as c:
            c.call('user.update', u1['id'], {'userns_idmap': 12345})
            try:
                with pytest.raises(ClientException, match='already maps to container UID 12345'):
                    c.call('user.update', u2['id'], {'userns_idmap': 12345})
            finally:
                c.call('user.update', u1['id'], {'userns_idmap': None})


def test__user_duplicate_direct_vs_explicit_deny():
    with create_user('idmap_dup_a') as u1, create_user('idmap_dup_b') as u2:
        with Client() as c:
            c.call('user.update', u1['id'], {'userns_idmap': 'DIRECT'})
            try:
                with pytest.raises(ClientException, match=f'already maps to container UID {u1["uid"]}'):
                    c.call('user.update', u2['id'], {'userns_idmap': u1['uid']})
            finally:
                c.call('user.update', u1['id'], {'userns_idmap': None})


def test__user_duplicate_explicit_vs_direct_deny():
    with create_user('idmap_dup_a') as u1, create_user('idmap_dup_b') as u2:
        with Client() as c:
            c.call('user.update', u1['id'], {'userns_idmap': u2['uid']})
            try:
                with pytest.raises(ClientException, match=f'already maps to container UID {u2["uid"]}'):
                    c.call('user.update', u2['id'], {'userns_idmap': 'DIRECT'})
            finally:
                c.call('user.update', u1['id'], {'userns_idmap': None})


def test__group_duplicate_explicit_idmap_deny():
    with Client() as c:
        g1_id = c.call('group.create', {'name': 'idmap_dup_grp_a'})
        try:
            g2_id = c.call('group.create', {'name': 'idmap_dup_grp_b'})
            try:
                c.call('group.update', g1_id, {'userns_idmap': 23456})
                try:
                    with pytest.raises(ClientException, match='already maps to container GID 23456'):
                        c.call('group.update', g2_id, {'userns_idmap': 23456})
                finally:
                    c.call('group.update', g1_id, {'userns_idmap': None})
            finally:
                c.call('group.delete', g2_id)
        finally:
            c.call('group.delete', g1_id)


def test__group_duplicate_direct_vs_explicit_deny():
    with Client() as c:
        g1_id = c.call('group.create', {'name': 'idmap_dup_grp_a'})
        try:
            g1 = c.call('group.query', [['id', '=', g1_id]], {'get': True})
            g2_id = c.call('group.create', {'name': 'idmap_dup_grp_b'})
            try:
                c.call('group.update', g1_id, {'userns_idmap': 'DIRECT'})
                try:
                    with pytest.raises(ClientException, match=f'already maps to container GID {g1["gid"]}'):
                        c.call('group.update', g2_id, {'userns_idmap': g1['gid']})
                finally:
                    c.call('group.update', g1_id, {'userns_idmap': None})
            finally:
                c.call('group.delete', g2_id)
        finally:
            c.call('group.delete', g1_id)


def test__user_self_update_keeps_idmap():
    with create_user('idmap_self') as u:
        with Client() as c:
            c.call('user.update', u['id'], {'userns_idmap': 'DIRECT'})
            try:
                # Re-asserting the same idmap should not flag self-collision.
                c.call('user.update', u['id'], {'userns_idmap': 'DIRECT'})
            finally:
                c.call('user.update', u['id'], {'userns_idmap': None})


def test__user_create_autoassigned_uid_idmap_conflict_deny():
    with Client() as c:
        placeholder = c.call('user.create', {
            'username': 'idmap_auto_placeholder', 'full_name': 'placeholder',
            'random_password': True, 'group_create': True,
        })
        target_uid = placeholder['uid']
        user_a = c.call('user.create', {
            'username': 'idmap_auto_a', 'full_name': 'a',
            'random_password': True, 'group_create': True,
            'userns_idmap': target_uid,
        })
        # Free target_uid so the next auto-assignment returns it (smallest gap).
        c.call('user.delete', placeholder['id'])
        try:
            user_b_id = None
            try:
                with pytest.raises(ClientException, match=f'already maps to container UID {target_uid}'):
                    user_b_id = c.call('user.create', {
                        'username': 'idmap_auto_b', 'full_name': 'b',
                        'random_password': True, 'group_create': True,
                        'userns_idmap': 'DIRECT',
                    })
            finally:
                if user_b_id is not None:
                    c.call('user.delete', user_b_id)
        finally:
            c.call('user.delete', user_a['id'])


def test__group_create_autoassigned_gid_idmap_conflict_deny():
    with Client() as c:
        placeholder_id = c.call('group.create', {'name': 'idmap_auto_grp_placeholder'})
        placeholder = c.call('group.query', [['id', '=', placeholder_id]], {'get': True})
        target_gid = placeholder['gid']
        g_a_id = c.call('group.create', {
            'name': 'idmap_auto_grp_a', 'userns_idmap': target_gid,
        })
        c.call('group.delete', placeholder_id)
        try:
            g_b_id = None
            try:
                with pytest.raises(ClientException, match=f'already maps to container GID {target_gid}'):
                    g_b_id = c.call('group.create', {
                        'name': 'idmap_auto_grp_b',
                        'userns_idmap': 'DIRECT',
                    })
            finally:
                if g_b_id is not None:
                    c.call('group.delete', g_b_id)
        finally:
            c.call('group.delete', g_a_id)
