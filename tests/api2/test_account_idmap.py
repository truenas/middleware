import os
import sys

import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import call, client

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
