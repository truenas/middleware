import json
import os
import pytest

from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.smb import security, smb_connection
from samba import ntstatus, NTSTATUSError


ADV_PERMS_FIELDS = [
    'READ_DATA', 'WRITE_DATA', 'APPEND_DATA',
    'READ_NAMED_ATTRS', 'WRITE_NAMED_ATTRS',
    'EXECUTE',
    'DELETE_CHILD', 'DELETE',
    'READ_ATTRIBUTES', 'WRITE_ATTRIBUTES',
    'READ_ACL', 'WRITE_ACL',
    'WRITE_OWNER',
    'SYNCHRONIZE'
]

NULL_DACL_PERMS = {'BASIC': 'FULL_CONTROL'}
EMPTY_DACL_PERMS = {perm: False for perm in ADV_PERMS_FIELDS}


@pytest.fixture(scope='function')
def share():
    with dataset('null_dacl_test', {'share_type': 'SMB'}) as ds:
        with smb_share(f'/mnt/{ds}', 'DACL_TEST_SHARE') as s:
            yield {'ds': ds, 'share': s}


def set_special_acl(path, special_acl_type):
    match special_acl_type:
        case 'NULL_DACL':
            permset = NULL_DACL_PERMS
        case 'EMPTY_DACL':
            permset = EMPTY_DACL_PERMS
        case _:
            raise TypeError(f'[EDOOFUS]: {special_acl_type} unexpected special ACL type')

    payload = json.dumps({'acl': [{
        'tag': 'everyone@',
        'id': -1,
        'type': 'ALLOW',
        'perms': permset,
        'flags': {'BASIC': 'NOINHERIT'},
    }]})
    ssh(f'touch {path}')

    # Use SSH to write to avoid middleware ACL normalization and validation
    # that prevents writing these specific ACLs.
    ssh(f"nfs4xdr_setfacl -j '{payload}' {path}")


def test_null_dacl_set(unprivileged_user_fixture, share):
    """ verify that setting NULL DACL results in expected ZFS ACL """
    with smb_connection(
        share=share['share']['name'],
        username=unprivileged_user_fixture.username,
        password=unprivileged_user_fixture.password,
    ) as c:
        fh = c.create_file('test_null_dacl', 'w')
        current_sd = c.get_sd(fh, security.SECINFO_OWNER | security.SECINFO_GROUP)
        current_sd.dacl = None
        c.set_sd(fh, current_sd, security.SECINFO_OWNER | security.SECINFO_GROUP | security.SECINFO_DACL)

        new_sd = c.get_sd(fh, security.SECINFO_OWNER | security.SECINFO_GROUP | security.SECINFO_DACL)
        assert new_sd.dacl is None

        theacl = call('filesystem.getacl', os.path.join(share['share']['path'], 'test_null_dacl'))
        assert len(theacl['acl']) == 1

        assert theacl['acl'][0]['perms'] == NULL_DACL_PERMS
        assert theacl['acl'][0]['type'] == 'ALLOW'
        assert theacl['acl'][0]['tag'] == 'everyone@'


def test_null_dacl_functional(unprivileged_user_fixture, share):
    """ verify that NULL DACL grants write privileges """
    testfile = os.path.join(share['share']['path'], 'test_null_dacl_write')
    set_special_acl(testfile, 'NULL_DACL')
    data = b'canary'

    with smb_connection(
        share=share['share']['name'],
        username=unprivileged_user_fixture.username,
        password=unprivileged_user_fixture.password,
    ) as c:
        fh = c.create_file('test_null_dacl_write', 'w')
        current_sd = c.get_sd(fh, security.SECINFO_OWNER | security.SECINFO_GROUP)
        assert current_sd.dacl is None

        c.write(fh, data)
        assert c.read(fh, 0, cnt=len(data)) == data


def test_empty_dacl_set(unprivileged_user_fixture, share):
    """ verify that setting empty DACL results in expected ZFS ACL """
    with smb_connection(
        share=share['share']['name'],
        username=unprivileged_user_fixture.username,
        password=unprivileged_user_fixture.password,
    ) as c:
        fh = c.create_file('test_empty_dacl', 'w')
        current_sd = c.get_sd(fh, security.SECINFO_OWNER | security.SECINFO_GROUP)
        current_sd.dacl = security.acl()
        c.set_sd(fh, current_sd, security.SECINFO_OWNER | security.SECINFO_GROUP | security.SECINFO_DACL)

        new_sd = c.get_sd(fh, security.SECINFO_OWNER | security.SECINFO_GROUP | security.SECINFO_DACL)
        assert new_sd.dacl.num_aces == 0

        theacl = call('filesystem.getacl', os.path.join(share['share']['path'], 'test_empty_dacl'))
        assert len(theacl['acl']) == 1

        assert theacl['acl'][0]['perms'] == EMPTY_DACL_PERMS
        assert theacl['acl'][0]['type'] == 'ALLOW'
        assert theacl['acl'][0]['tag'] == 'everyone@'


def test_empty_dacl_functional(unprivileged_user_fixture, share):
    testfile = os.path.join(share['share']['path'], 'test_empty_dacl_write')
    set_special_acl(testfile, 'EMPTY_DACL')

    with smb_connection(
        share=share['share']['name'],
        username=unprivileged_user_fixture.username,
        password=unprivileged_user_fixture.password,
    ) as c:
        # File has empty ACL and is not owned by this user
        with pytest.raises(NTSTATUSError) as nt_err:
            c.create_file('test_empty_dacl_write', 'w')

        assert nt_err.value.args[0] == ntstatus.NT_STATUS_ACCESS_DENIED
