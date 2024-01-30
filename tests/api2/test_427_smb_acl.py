#!/usr/bin/env python3

import pytest
import sys
import os
import secrets
import string
import subprocess
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import (
    ip,
    pool_name,
)
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from protocols import SMB
from pytest_dependency import depends
from time import sleep
from utils import create_dataset


SMB_USER = "smbacluser"
SMB_PWD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))
TEST_DATA = {}
pytestmark = pytest.mark.smb


permset = {
    "READ_DATA": False,
    "WRITE_DATA": False,
    "APPEND_DATA": False,
    "READ_NAMED_ATTRS": False,
    "WRITE_NAMED_ATTRS": False,
    "EXECUTE": False,
    "DELETE_CHILD": False,
    "READ_ATTRIBUTES": False,
    "WRITE_ATTRIBUTES": False,
    "DELETE": False,
    "READ_ACL": False,
    "WRITE_ACL": False,
    "WRITE_OWNER": False,
    "SYNCHRONIZE": True
}

flagset = {
    "FILE_INHERIT": False,
    "DIRECTORY_INHERIT": False,
    "INHERIT_ONLY": False,
    "NO_PROPAGATE_INHERIT": False,
    "INHERITED": False
}


def get_windows_sd(share, format="LOCAL"):
    return call("smb.get_remote_acl", {
        "server": "127.0.0.1",
        "share": share,
        "username": SMB_USER,
        "password": SMB_PWD,
        "options": {"output_format": format}
    })['acl_data']


def iter_permset(path, share, local_acl):
    smbacl = get_windows_sd(share)
    assert smbacl['acl'][0]['perms'] == permset
    for perm in permset.keys():
        permset[perm] = True
        call('filesystem.setacl', {'path': path, "dacl": local_acl}, job=True)
        smbacl = get_windows_sd(share)
        for ace in smbacl["acl"]:
            if ace["id"] != 666:
                continue

            assert ace["perms"] == permset, f'{perm}: {str(ace)}'


def iter_flagset(path, share, local_acl):
    smbacl = get_windows_sd(share)
    assert smbacl['acl'][0]['flags'] == flagset
    for flag in flagset.keys():
        # we automatically canonicalize entries and so INHERITED shifts to end of list
        flagset[flag] = True
        call('filesystem.setacl', {'path': path, "dacl": local_acl}, job=True)
        smbacl = get_windows_sd(share)
        for ace in smbacl["acl"]:
            if ace["id"] != 666:
                continue

            assert ace["flags"] == flagset, f'{flag}: {str(ace)}'


@pytest.fixture(scope='module')
def initialize_for_smb_tests(request):
    ba = call(
        'group.query',
        [['name', '=', 'builtin_administrators']],
        {'get': True}
    )
    with user({
        'username': SMB_USER,
        'full_name': SMB_USER,
        'group_create': True,
        'smb': True,
        'groups': [ba['id']],
        'password': SMB_PWD
    }) as u:
        try:
            call('service.start', 'cifs')
            yield {'user': u}
        finally:
            call('service.stop', 'cifs')


@pytest.mark.dependency(name="SMB_SERVICE_STARTED")
def test_001_initialize_for_tests(initialize_for_smb_tests):
    TEST_DATA.update(initialize_for_smb_tests)


def test_003_test_perms(request):
    """
    This test creates a temporary dataset / SMB share,
    then iterates through all the possible permissions bits
    setting local FS ace for each of them and verifies that
    correct NT ACL bit gets toggled when viewed through SMB
    protocol.
    """
    depends(request, ["SMB_SERVICE_STARTED"], scope="session")

    with dataset('nfs4acl_perms_smb', {'share_type': 'SMB'}) as ds:
        path = os.path.join('/mnt', ds)
        with smb_share(path, "PERMS"):
            the_acl = call('filesystem.getacl', path, False)['acl']
            the_acl.insert(0, {
                'perms': permset,
                'flags': flagset,
                'id': 666,
                'type': 'ALLOW',
                'tag': 'USER'
            })
            call('filesystem.setacl', {'path': path, "dacl": the_acl}, job=True)
            iter_permset(path, "PERMS", the_acl)


def test_004_test_flags(request):
    """
    This test creates a temporary dataset / SMB share,
    then iterates through all the possible inheritance flags
    setting local FS ace for each of them and verifies that
    correct NT ACL bit gets toggled when viewed through SMB
    protocol.
    """
    depends(request, ["SMB_SERVICE_STARTED"], scope="session")

    with dataset('nfs4acl_flags_smb', {'share_type': 'SMB'}) as ds:
        path = os.path.join('/mnt', ds)
        with smb_share(path, "FLAGS"):
            the_acl = call('filesystem.getacl', path, False)['acl']
            the_acl.insert(0, {
                'perms': permset,
                'flags': flagset,
                'id': 666,
                'type': 'ALLOW',
                'tag': 'USER'
            })
            call('filesystem.setacl', {'path': path, "dacl": the_acl}, job=True)
            iter_flagset(path, "FLAGS", the_acl)


def test_005_test_map_modify(request):
    """
    This test validates that we are generating an appropriate SD when user has
    'stripped' an ACL from an SMB share. Appropriate in this case means one that
    grants an access mask equaivalent to MODIFY or FULL depending on whether it's
    the file owner or group / other.
    """
    depends(request, ["SMB_SERVICE_STARTED"], scope="session")

    ds = 'nfs4acl_map_modify'
    path = f'/mnt/{pool_name}/{ds}'
    with create_dataset(f'{pool_name}/{ds}', {'acltype': 'NFSV4', 'aclmode': 'PASSTHROUGH'}, None, 777):
        with smb_share(path, "MAP_MODIFY"):
            sd = get_windows_sd("MAP_MODIFY", "SMB")
            dacl = sd['dacl']
            assert dacl[0]['access_mask']['standard'] == 'FULL', str(dacl[0])
            assert dacl[1]['access_mask']['special']['WRITE_ATTRIBUTES'], str(dacl[1])
            assert dacl[1]['access_mask']['special']['WRITE_EA'], str(dacl[1])
            assert dacl[2]['access_mask']['special']['WRITE_ATTRIBUTES'], str(dacl[2])
            assert dacl[2]['access_mask']['special']['WRITE_EA'], str(dacl[2])


def test_006_test_preserve_dynamic_id_mapping(request):
    depends(request, ["SMB_SERVICE_STARTED"], scope="session")

    def _find_owner_rights(acl):
        for entry in acl:
            if 'owner rights' in entry['who']:
                return True

        return False

    ds = 'nfs4acl_dynmamic_user'
    path = f'/mnt/{pool_name}/{ds}'
    with create_dataset(f'{pool_name}/{ds}', {'share_type': 'SMB'}):
        with smb_share(path, "DYNAMIC"):
            # add an ACL entry that forces generation
            # of a dynamic idmap entry
            sleep(5)
            cmd = [
                'smbcacls',
                f'//{ip}/DYNAMIC',
                '\\',
                '-a', r'ACL:S-1-3-4:ALLOWED/0x0/FULL',
                '-d', '0',
                '-U', f'{SMB_USER}%{SMB_PWD}',
            ]
            res = subprocess.run(cmd, capture_output=True)
            assert res.returncode == 0, res.stderr.decode() or res.stdout.decode()

            # verify "owner rights" entry is present
            # verify "owner rights" entry is still present
            the_acl = call('filesystem.getacl', path, False, True)['acl']
            has_owner_rights = _find_owner_rights(the_acl)
            assert has_owner_rights is True, str(the_acl)

            # force re-sync of group mapping database (and winbindd_idmap.tdb)
            call('smb.synchronize_group_mappings', job=True)

            # verify "owner rights" entry is still present
            the_acl = call('filesystem.getacl', path, False, True)['acl']
            has_owner_rights = _find_owner_rights(the_acl)
            assert has_owner_rights is True, str(the_acl)


def test_007_test_disable_autoinherit(request):
    depends(request, ["SMB_SERVICE_STARTED"], scope="session")
    ds = 'nfs4acl_disable_inherit'
    path = f'/mnt/{pool_name}/{ds}'
    with create_dataset(f'{pool_name}/{ds}', {'share_type': 'SMB'}):
        with smb_share(path, 'NFS4_INHERIT'):
            c = SMB()
            c.connect(host=ip, share='NFS4_INHERIT', username=SMB_USER, password=SMB_PWD, smb1=False)
            c.mkdir('foo')
            sd = c.get_sd('foo')
            assert 'SEC_DESC_DACL_PROTECTED' not in sd['control']['parsed'], str(sd)
            c.inherit_acl('foo', 'COPY')
            sd = c.get_sd('foo')
            assert 'SEC_DESC_DACL_PROTECTED' in sd['control']['parsed'], str(sd)
            c.disconnect()
