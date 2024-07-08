import pytest

from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.account import group

BASE_RID_GROUP = 200000


@pytest.mark.parametrize('groupname,expected_memberof,expected_rid', [
    ('builtin_administrators', 'S-1-5-32-544', 512),
    ('builtin_guests', 'S-1-5-32-546', 514)
])
def test__local_builtin_accounts(groupname, expected_memberof, expected_rid):
    entry = call('group.query', [['group', '=', groupname]], {'get': True})
    rid = int(entry['sid'].split('-')[-1])
    assert rid == expected_rid

    groupmap = call('smb.groupmap_list')
    assert str(entry['gid']) in groupmap['local_builtins']
    assert groupmap['local_builtins'][str(entry['gid'])]['sid'] == entry['sid']

    members = call('smb.groupmap_listmem', expected_memberof)
    assert entry['sid'] in members


def test__local_builtin_users_account():
    entry = call('group.query', [['group', '=', 'builtin_users']], {'get': True})

    rid = int(entry['sid'].split('-')[-1])
    assert rid == entry['id'] + BASE_RID_GROUP

    members_dom_users = call('smb.groupmap_listmem', 'S-1-5-32-545')
    assert entry['sid'] in members_dom_users


def test__new_group():
    with group({"name": "group1"}) as g:
        # Validate GID is being assigned as expected
        assert g['sid'] is not None
        rid = int(g['sid'].split('-')[-1])
        assert rid == g['id'] + BASE_RID_GROUP

        groupmap = call('smb.groupmap_list')

        assert groupmap['local'][str(g['gid'])]['sid'] == g['sid']

        # Validate that disabling SMB removes SID value from query results
        call('group.update', g['id'], {'smb': False})

        new = call('group.get_instance', g['id'])
        assert new['sid'] is None

        # Check for presence in group_mapping.tdb
        groupmap = call('smb.groupmap_list')
        assert new['gid'] not in groupmap['local']

        # Validate that re-enabling restores SID value
        call('group.update', g['id'], {'smb': True})
        new = call('group.get_instance', g['id'])
        assert new['sid'] == g['sid']

        groupmap = call('smb.groupmap_list')
        assert str(new['gid']) in groupmap['local']


@pytest.mark.parametrize('name,gid,sid', [
    ('Administrators', 90000001, 'S-1-5-32-544'),
    ('Users', 90000002, 'S-1-5-32-545'),
    ('Guests', 90000003, 'S-1-5-32-546')
])
def test__builtins(name, gid, sid):
    builtins = call('smb.groupmap_list')['builtins']
    assert str(gid) in builtins
