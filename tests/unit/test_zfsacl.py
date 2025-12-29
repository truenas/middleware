import os
import pwd
import pytest
import shutil
import truenas_pylibzfs
import zfsacl
from contextlib import contextmanager
from truenas_api_client import Client, ClientException


@pytest.fixture(scope='module')
def local_user():
    with Client() as c:
        usr = c.call('user.create', {
            'username': 'test_local_user',
            'full_name': 'test_local_user',
            'random_password': True,
            'group_create': True
        })
        try:
            yield usr

        finally:
            c.call('user.delete', usr['id'])


@pytest.fixture(scope='module')
def create_dataset():
    """ create an nfsv4 dataset under /var for basic functional testing """
    with Client() as c:
        mnt = c.call('filesystem.mount_info', [['mountpoint', '=', '/var']], {'get': True})

    lz = truenas_pylibzfs.open_handle()
    ds_name = f'{mnt["mount_source"]}/nfsv4'
    lz.create_resource(name=ds_name, type=truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM, properties={
        truenas_pylibzfs.ZFSProperty.ACLTYPE: 'nfsv4',
        truenas_pylibzfs.ZFSProperty.ACLMODE: 'restricted',
    })
    rsrc = lz.open_resource(name=ds_name)
    try:
        rsrc.mount()
        yield rsrc
    finally:
        rsrc.unmount()
        lz.destroy_resource(name=ds_name)


@pytest.fixture(scope='function')
def testdir(create_dataset):
    os.mkdir('/var/nfsv4/testdir')

    try:
        yield '/var/nfsv4/testdir'
    finally:
        shutil.rmtree('/var/nfsv4/testdir')


@contextmanager
def run_as_user(username: str):
    """
    Temporarily assume the identity of `username`
    (uid, gid, and supplementary groups), then restore.

    Must be run as root.
    """

    # Save original credentials
    orig_euid = os.geteuid()
    orig_egid = os.getegid()
    orig_groups = os.getgroups()

    pw = pwd.getpwnam(username)

    try:
        # Drop privileges (order matters)
        os.setgroups([])
        os.initgroups(pw.pw_name, pw.pw_gid)
        os.setegid(pw.pw_gid)
        os.seteuid(pw.pw_uid)

        yield

    finally:
        # Restore original credentials (reverse order)
        os.seteuid(orig_euid)
        os.setegid(orig_egid)
        os.setgroups(orig_groups)


def test_chown(local_user, testdir):
    """ basic test that with trivial ACL owner cannot by default chown """
    os.chown(testdir, local_user['uid'], -1)
    current_acl = zfsacl.Acl(path=testdir)
    # This should be a trivial ACL
    assert current_acl.acl_flags & zfsacl.ACL_IS_TRIVIAL != 0

    # Trivial ACL should not permit chown
    with run_as_user(local_user['username']):
        with pytest.raises(PermissionError):
            os.chown(testdir, 0, -1)


    # now let's add an ACL entry that groups our current user full control
    entry = current_acl.create_entry()
    entry.entry_type = zfsacl.ENTRY_TYPE_ALLOW
    entry.permset = zfsacl.BASIC_PERM_FULL_CONTROL
    entry.who = (zfsacl.WHOTYPE_USER, local_user['uid'])
    current_acl.setacl(path=testdir)

    # This should succeed since we've explicitly granted this user permissions
    # to chown files
    with run_as_user(local_user['username']):
        os.chown(testdir, 0, -1)
