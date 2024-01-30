import os
import pytest

from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share, smb_mount
from middlewared.test.integration.utils import call, client, ssh


PERMSET = {
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

SAMPLE_ENTRY = {
    "tag": "GROUP",
    "id": 666,
    "type": "ALLOW",
    "perms": PERMSET,
    "flags": {"BASIC": "INHERIT"}
}

PERSISTENT_ACL = [
    {
        "tag": "GROUP",
        "id": 545,
        "type": "ALLOW",
        "perms": {"BASIC": "FULL_CONTROL"},
        "flags": {"BASIC": "INHERIT"}
    }
]

TMP_SMB_USER_PASSWORD = 'Abcd1234$'
pytestmark = pytest.mark.smb


@pytest.fixture(scope='module')
def setup_smb_tests(request):
    with dataset('smbclient-testing', data={'share_type': 'SMB'}) as ds:
        with user({
            'username': 'smbuser',
            'full_name': 'smbuser',
            'group_create': True,
            'password': TMP_SMB_USER_PASSWORD
        }) as u:
            with smb_share(os.path.join('/mnt', ds), 'client_share') as s:
                try:
                    call('service.start', 'cifs')
                    yield {'dataset': ds, 'share': s, 'user': u}
                finally:
                    call('service.stop', 'cifs')


@pytest.fixture(scope='module')
def mount_share(setup_smb_tests):
    with smb_mount(setup_smb_tests['share']['name'], 'smbuser', TMP_SMB_USER_PASSWORD) as mp:
        yield setup_smb_tests | {'mountpoint': mp}


def compare_acls(local_path, share_path):
    local_acl = call('filesystem.getacl', local_path)
    local_acl.pop('path')
    smb_acl = call('filesystem.getacl', share_path)
    smb_acl.pop('path')
    assert local_acl == smb_acl


def test_smb_mount(request, mount_share):
    assert call('filesystem.statfs', mount_share['mountpoint'])['fstype'] == 'cifs'


def test_acl_share_root(request, mount_share):
    compare_acls(mount_share['share']['path'], mount_share['mountpoint'])


def test_acl_share_subdir(request, mount_share):
    call('filesystem.mkdir', {
        'path': os.path.join(mount_share['share']['path'], 'testdir'),
        'options': {'raise_chmod_error': False},
    })

    compare_acls(
        os.path.join(mount_share['share']['path'], 'testdir'),
        os.path.join(mount_share['mountpoint'], 'testdir')
    )


def test_acl_share_file(request, mount_share):
    ssh(f'touch {os.path.join(mount_share["share"]["path"], "testfile")}')

    compare_acls(
        os.path.join(mount_share['share']['path'], 'testfile'),
        os.path.join(mount_share['mountpoint'], 'testfile')
    )


@pytest.mark.parametrize('perm', PERMSET.keys())
def test_acl_share_permissions(request, mount_share, perm):
    assert call('filesystem.statfs', mount_share['mountpoint'])['fstype'] == 'cifs'

    SAMPLE_ENTRY['perms'] | {perm: True}
    payload = {
        'path': mount_share['share']['path'],
        'dacl': [SAMPLE_ENTRY] + PERSISTENT_ACL
    }
    call('filesystem.setacl', payload, job=True)
    compare_acls(mount_share['share']['path'], mount_share['mountpoint'])


@pytest.mark.parametrize('flagset', [
    {
        'FILE_INHERIT': True,
        'DIRECTORY_INHERIT': True,
        'NO_PROPAGATE_INHERIT': False,
        'INHERIT_ONLY': False,
        'INHERITED': False,
    },
    {
        'FILE_INHERIT': True,
        'DIRECTORY_INHERIT': False,
        'NO_PROPAGATE_INHERIT': False,
        'INHERIT_ONLY': False,
        'INHERITED': False,
    },
    {
        'FILE_INHERIT': False,
        'DIRECTORY_INHERIT': True,
        'NO_PROPAGATE_INHERIT': False,
        'INHERIT_ONLY': False,
        'INHERITED': False,
    },
    {
        'FILE_INHERIT': False,
        'DIRECTORY_INHERIT': False,
        'NO_PROPAGATE_INHERIT': False,
        'INHERIT_ONLY': False,
        'INHERITED': False,
    },
    {
        'FILE_INHERIT': True,
        'DIRECTORY_INHERIT': False,
        'NO_PROPAGATE_INHERIT': False,
        'INHERIT_ONLY': True,
        'INHERITED': False,
    },
    {
        'FILE_INHERIT': False,
        'DIRECTORY_INHERIT': True,
        'NO_PROPAGATE_INHERIT': False,
        'INHERIT_ONLY': True,
        'INHERITED': False,
    },
    {
        'FILE_INHERIT': True,
        'DIRECTORY_INHERIT': False,
        'NO_PROPAGATE_INHERIT': True,
        'INHERIT_ONLY': True,
        'INHERITED': False,
    },
    {
        'FILE_INHERIT': False,
        'DIRECTORY_INHERIT': True,
        'NO_PROPAGATE_INHERIT': True,
        'INHERIT_ONLY': True,
        'INHERITED': False,
    }
])
def test_acl_share_flags(request, mount_share, flagset):
    assert call('filesystem.statfs', mount_share['mountpoint'])['fstype'] == 'cifs'

    SAMPLE_ENTRY['flags'] = flagset
    payload = {
        'path': mount_share['share']['path'],
        'dacl': [SAMPLE_ENTRY] + PERSISTENT_ACL
    }
    call('filesystem.setacl', payload, job=True)
    compare_acls(mount_share['share']['path'], mount_share['mountpoint'])
