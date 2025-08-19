import pytest

from middlewared.test.integration.assets.account import group, user
from middlewared.test.integration.utils import call

from middlewared.service_exception import ValidationErrors

LOCAL_USER_SID_PREFIX = 'S-1-22-1-'
LOCAL_GROUP_SID_PREFIX = 'S-1-22-2-'


def test_uid_idmapping():
    with user({
        'username': 'idmap_user',
        'full_name': 'idmap_user',
        'smb': True,
        'group_create': True,
        'password': 'test1234',
    }) as u:
        UNIX_SID = LOCAL_USER_SID_PREFIX + str(u['uid'])
        results = call('idmap.convert_sids', [UNIX_SID])
        assert results['unmapped'] == {}
        assert UNIX_SID in results['mapped']

        entry = results['mapped'][UNIX_SID]

        assert entry['id_type'] == 'USER'
        assert entry['id'] == u['uid']
        assert entry['name'] == 'Unix User\\idmap_user'

        results = call('idmap.convert_unixids', [{
            'id_type': 'USER',
            'id': u['uid'],
        }])

        assert results['unmapped'] == {}
        entry = results['mapped'][f'UID:{u["uid"]}']
        assert entry['id_type'] == 'USER'
        assert entry['id'] == u['uid']
        pdb_sid = entry['sid']

        user_obj = call('user.get_user_obj', {'uid': u['uid'], 'sid_info': True})
        assert 'sid' in user_obj
        assert user_obj['sid'] == pdb_sid


def test_unsetting_immutable_idmaps():
    # User
    app_uid = call('user.query', [['username', '=', 'apps']], {'get': True})['id']
    with pytest.raises(ValidationErrors) as ve:
        call('user.update', app_uid, {'userns_idmap': None})
    assert ve.value.errors[0].errmsg == 'This attribute cannot be changed'

    # Group
    app_gid = call('group.query', [['group', '=', 'apps']], {'get': True})['id']
    with pytest.raises(ValidationErrors) as ve:
        call('group.update', app_gid, {'userns_idmap': None})
    assert ve.value.errors[0].errmsg == 'User namespace idmaps may not be configured for builtin accounts.'


def test_mutable_idmaps():
    with group({'name': 'dummy_group'}) as g:
        with user({
            'username': 'dummy_user',
            'full_name': 'dummy_user',
            'smb': True,
            'password': 'test1234',
            'group': g['id'],
        }) as u:
            call('user.update', u['id'], {'userns_idmap': 'DIRECT'})
            call('group.update', g['id'], {'userns_idmap': 'DIRECT'})

            user_response = call('user.update', u['id'], {'userns_idmap': None})
            group_response = call('group.update', g['id'], {'userns_idmap': None})

            assert user_response['id'] == u['id']
            assert group_response == g['id']
