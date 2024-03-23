import os
import sys

import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import call, client

LOCAL_USER_SID_PREFIX = 'S-1-22-1-'
LOCAL_GROUP_SID_PREFIX = 'S-1-22-2-'
pytestmark = pytest.mark.accounts

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

        # This test validates that our winbindd cache
        # is not populated with special unix account sid
        pdb_sid = call('idmap.name_to_sid', 'idmap_user')['sid']
        assert pdb_sid != UNIX_SID

        results = call('idmap.convert_unixids', [{
            'id_type': 'USER',
            'id': u['uid'],
        }])

        assert results['unmapped'] == {}
        entry = results['mapped'][f'UID:{u["uid"]}']
        assert entry['id_type'] == 'USER'
        assert entry['id'] == u['uid']
        assert entry['sid'] == pdb_sid

        user_obj = call('user.get_user_obj', {'uid': u['uid'], 'sid_info': True})
        assert 'sid_info' in user_obj
        sid_info = user_obj['sid_info']
        assert sid_info['sid'] == pdb_sid

        assert 'domain_information' in sid_info
        domain_info = sid_info['domain_information']
        assert domain_info['online']
        assert not domain_info['activedirectory']
        assert pdb_sid.startswith(domain_info['domain_sid'])
