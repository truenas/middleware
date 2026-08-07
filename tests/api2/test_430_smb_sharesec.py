import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from middlewared.test.integration.assets.account import user as create_user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.utils.legacy_functions import SSH_TEST
from auto_config import user, password

Guests = {
    "domain": "BUILTIN",
    "name": "Guests",
    "sidtype": "ALIAS"
}
Admins = {
    "domain": "BUILTIN",
    "name": "Administrators",
    "sidtype": "ALIAS"
}
Users = {
    "domain": "BUILTIN",
    "name": "Users",
    "sidtype": "ALIAS"
}


@pytest.fixture(scope="module")
def setup_smb_share():
    with dataset(
        "smb-sharesec",
        {'share_type': 'SMB'},
    ) as ds:
        with smb_share(f'/mnt/{ds}', "my_sharesec") as share:
            yield share


@pytest.fixture(scope="module")
def sharesec_user():
    with create_user({
        'username': 'sharesec_user',
        'full_name': 'sharesec_user',
        'smb': True,
        'group_create': True,
        'password': 'test1234',
    }) as u:
        yield u


def test_initialize_share(setup_smb_share):
    acl = call('sharing.smb.getacl', {'share_name': setup_smb_share['name']})
    assert acl['share_name'].casefold() == setup_smb_share['name'].casefold()
    assert len(acl['share_acl']) == 1
    assert acl['share_acl'][0]['ae_who_sid'] == 'S-1-1-0'
    assert acl['share_acl'][0]['ae_perm'] == 'FULL'
    assert acl['share_acl'][0]['ae_type'] == 'ALLOWED'


def test_set_smb_acl_by_sid(setup_smb_share):
    payload = {
        'share_name': setup_smb_share['name'],
        'share_acl': [
            {
                'ae_who_sid': 'S-1-5-32-545',
                'ae_perm': 'FULL',
                'ae_type': 'ALLOWED'
            }
        ]
    }
    acl_set = call('sharing.smb.setacl', payload)

    assert payload['share_name'].casefold() == acl_set['share_name'].casefold()
    assert payload['share_acl'][0]['ae_who_sid'] == acl_set['share_acl'][0]['ae_who_sid']
    assert payload['share_acl'][0]['ae_perm'] == acl_set['share_acl'][0]['ae_perm']
    assert payload['share_acl'][0]['ae_type'] == acl_set['share_acl'][0]['ae_type']
    assert acl_set['share_acl'][0]['ae_who_id']['id_type'] == 'GROUP'

    b64acl = call(
        'datastore.query', 'sharing.cifs.share',
        [['cifs_name', '=', setup_smb_share['name']]],
        {'get': True}
    )['cifs_share_acl']

    assert b64acl != ""

    call('smb.sharesec.synchronize_acls')

    newb64acl = call(
        'datastore.query', 'sharing.cifs.share',
        [['cifs_name', '=', setup_smb_share['name']]],
        {'get': True}
    )['cifs_share_acl']

    assert newb64acl == b64acl


def test_set_smb_acl_by_unix_id(setup_smb_share, sharesec_user):
    payload = {
        'share_name': setup_smb_share['name'],
        'share_acl': [
            {
                'ae_who_id': {'id_type': 'USER', 'id': sharesec_user['uid']},
                'ae_perm': 'CHANGE',
                'ae_type': 'ALLOWED'
            }
        ]
    }
    acl_set = call('sharing.smb.setacl', payload)

    assert payload['share_name'].casefold() == acl_set['share_name'].casefold()
    assert payload['share_acl'][0]['ae_perm'] == acl_set['share_acl'][0]['ae_perm']
    assert payload['share_acl'][0]['ae_type'] == acl_set['share_acl'][0]['ae_type']
    assert acl_set['share_acl'][0]['ae_who_id']['id_type'] == 'USER'
    assert acl_set['share_acl'][0]['ae_who_id']['id'] == sharesec_user['uid']
    assert acl_set['share_acl'][0]['ae_who_str'] == sharesec_user['username']


def test_delete_share_info_tdb(setup_smb_share):
    cmd = 'rm /var/lib/truenas-samba/share_info.tdb'
    results = SSH_TEST(cmd, user, password)
    assert results['result'] is True, results['output']

    cmd = 'test -f /var/lib/truenas-samba/share_info.tdb'
    results = SSH_TEST(cmd, user, password)
    assert results['result'] is False, results['output']

    acl = call('sharing.smb.getacl', {'share_name': setup_smb_share['name']})
    assert acl['share_name'].casefold() == setup_smb_share['name'].casefold()
    assert acl['share_acl'][0]['ae_who_sid'] == 'S-1-1-0'


def test_restore_sharesec_with_flush_share_info(setup_smb_share, sharesec_user):
    with client() as c:
        c.call('smb.sharesec.flush_share_info')

    acl = call('sharing.smb.getacl', {'share_name': setup_smb_share['name']})
    assert acl['share_name'].casefold() == setup_smb_share['name'].casefold()
    assert acl['share_acl'][0]['ae_who_str'] == sharesec_user['username']


def test_verify_share_info_tdb_is_created(setup_smb_share, sharesec_user):
    cmd = 'test -f /var/lib/truenas-samba/share_info.tdb'
    results = SSH_TEST(cmd, user, password)
    assert results['result'] is True, results['output']

    # Get the initial ACL information
    acl = call('sharing.smb.getacl', {'share_name': setup_smb_share['name']})
    assert acl['share_name'].casefold() == setup_smb_share['name'].casefold()
    assert acl['share_acl'][0]['ae_who_str'] == sharesec_user['username']

    share = call('sharing.smb.query', [['id', '=', setup_smb_share['id']]], {'get': True})
    assert share['name'] == setup_smb_share['name']

    share = call('sharing.smb.update', setup_smb_share['id'], {'name': 'my_sharesec2'})
    assert share['name'] == 'my_sharesec2'

    acl = call('sharing.smb.getacl', {'share_name': 'my_sharesec2'})

    setup_smb_share['name'] = 'my_sharesec2'
    assert acl['share_name'].casefold() == setup_smb_share['name'].casefold()
    assert acl['share_acl'][0]['ae_who_str'] == sharesec_user['username'], ssh('tdbdump /var/lib/truenas-samba/share_info.tdb')


def test_toggle_share_and_verify_acl_preserved(setup_smb_share, sharesec_user):
    call('sharing.smb.update', setup_smb_share['id'], {"enabled": False})

    call('sharing.smb.update', setup_smb_share['id'], {"enabled": True})

    acl = call('sharing.smb.getacl', {'share_name': 'my_sharesec2'})
    assert acl['share_name'].casefold() == setup_smb_share['name'].casefold()
    assert acl['share_acl'][0]['ae_who_str'] == sharesec_user['username']


def test_removed_user(setup_smb_share):
    with create_user({
        'username': 'delme',
        'full_name': 'delme',
        'smb': True,
        'group_create': True,
        'password': 'test1234',
    }) as u:
        sid = u['sid']
        call('sharing.smb.setacl', {
            'share_name': setup_smb_share['name'],
            'share_acl': [{
                'ae_who_sid': u['sid'],
                'ae_perm': 'FULL',
                'ae_type': 'ALLOWED'
            }]
        })

    acl = call('sharing.smb.getacl', {'share_name': setup_smb_share['name']})
    assert acl['share_acl'][0]['ae_who_sid'] == sid
    assert acl['share_acl'][0]['ae_who_id'] is None
    assert acl['share_acl'][0]['ae_who_str'] is None


def test_restore_via_synchronize(setup_smb_share):
    with create_user({
        'username': 'delme',
        'full_name': 'delme',
        'smb': True,
        'group_create': True,
        'password': 'test1234',
    }) as u:
        sid = u['sid']
        call('sharing.smb.setacl', {
            'share_name': setup_smb_share['name'],
            'share_acl': [{
                'ae_who_sid': u['sid'],
                'ae_perm': 'FULL',
                'ae_type': 'ALLOWED'
            }]
        })

        acl = call('sharing.smb.getacl', {'share_name': setup_smb_share['name']})
        assert acl['share_acl'][0]['ae_who_sid'] == sid

        # Remove and be very certain share_info.tdb file is removed
        ssh('rm /var/lib/truenas-samba/share_info.tdb')
        assert call('smb.sharesec.entries') == []

        acl = call('sharing.smb.getacl', {'share_name': setup_smb_share['name']})
        assert acl['share_acl'][0]['ae_who_sid'] == 'S-1-1-0'

        # trigger ACL sync to rebuild
        call('smb.sharesec.synchronize_acls')

        # Verify we got it back
        acl = call('sharing.smb.getacl', {'share_name': setup_smb_share['name']})
        assert acl['share_acl'][0]['ae_who_sid'] == sid


@pytest.fixture(scope="module")
def legacy_acl_share():
    with dataset(
        "smb-sharesec-legacy",
        {'share_type': 'SMB'},
    ) as ds:
        with smb_share(f'/mnt/{ds}', "my_sharesec_legacy") as share:
            yield share


def set_legacy_share_acl(share, aclstr):
    """ Write a TrueNAS CORE format share ACL directly into the config database """
    call(
        'datastore.update', 'sharing.cifs_share', share['id'],
        {'cifs_share_acl': aclstr}
    )


@pytest.mark.parametrize('aclstr,expected', [
    # A security descriptor for a single well-known SID packs into a short byte string
    # that contains no base64 alphabet characters, so an encoding mismatch on it yields
    # an empty value rather than an error.
    (
        'S-1-1-0:ALLOWED/0x0/FULL',
        [{'ae_who_sid': 'S-1-1-0', 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'}],
    ),
    (
        'S-1-5-32-544:ALLOWED/0x0/FULL',
        [{'ae_who_sid': 'S-1-5-32-544', 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'}],
    ),
    (
        'S-1-5-32-544:ALLOWED/0x0/FULL S-1-5-32-545:ALLOWED/0x0/READ',
        [
            {'ae_who_sid': 'S-1-5-32-544', 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'},
            {'ae_who_sid': 'S-1-5-32-545', 'ae_perm': 'READ', 'ae_type': 'ALLOWED'},
        ],
    ),
])
def test_flush_legacy_share_acl(legacy_acl_share, aclstr, expected):
    """ Share ACLs migrated from TrueNAS CORE are stored as a space-delimited string
    rather than a packed security descriptor and must be converted on flush. """
    set_legacy_share_acl(legacy_acl_share, aclstr)

    call('smb.sharesec.flush_share_info')

    entry = call(
        'smb.sharesec.entries',
        [['key', '=', f'SECDESC/{legacy_acl_share["name"].lower()}']],
        {'get': True}
    )
    assert entry['value'] != ''

    acl = call('sharing.smb.getacl', {'share_name': legacy_acl_share['name']})
    assert len(acl['share_acl']) == len(expected)
    for idx, ace in enumerate(expected):
        assert acl['share_acl'][idx]['ae_who_sid'] == ace['ae_who_sid']
        assert acl['share_acl'][idx]['ae_perm'] == ace['ae_perm']
        assert acl['share_acl'][idx]['ae_type'] == ace['ae_type']


def test_legacy_share_acl_converted_in_config(legacy_acl_share):
    """ Once flushed, the legacy string in the config database is replaced by the
    packed security descriptor read back out of share_info.tdb. """
    set_legacy_share_acl(legacy_acl_share, 'S-1-5-32-544:ALLOWED/0x0/CHANGE')

    call('smb.sharesec.flush_share_info')
    call('smb.sharesec.synchronize_acls')

    stored = call(
        'datastore.query', 'sharing.cifs_share',
        [['id', '=', legacy_acl_share['id']]],
        {'get': True}
    )['cifs_share_acl']

    assert stored != ''
    assert not stored.startswith('S-1-')

    acl = call('sharing.smb.getacl', {'share_name': legacy_acl_share['name']})
    assert acl['share_acl'][0]['ae_who_sid'] == 'S-1-5-32-544'
    assert acl['share_acl'][0]['ae_perm'] == 'CHANGE'
