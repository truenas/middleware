"""
Functional permission-enforcement tests for NFS4 ACLs and POSIX mode bits.

These tests run locally on the NAS, create real ZFS datasets, set ACLs or
mode bits directly via truenas_os / os.chmod, then drop privileges with
os.seteuid to verify that the kernel allows or denies the operations as
expected.

Coverage mirrors the deleted tests/api2/test_345_acl_nfs4.py and
tests/api2/test_347_posix_mode.py.
"""

import os
import pwd
import stat
import shutil
import subprocess
import tempfile

import pytest
import truenas_os as t
from contextlib import contextmanager
from truenas_api_client import Client

import truenas_pylibzfs


# ── NFS4 permission masks ─────────────────────────────────────────────────────

_NFS4_FULL = (
    t.NFS4Perm.READ_DATA | t.NFS4Perm.WRITE_DATA |
    t.NFS4Perm.APPEND_DATA | t.NFS4Perm.READ_NAMED_ATTRS |
    t.NFS4Perm.WRITE_NAMED_ATTRS | t.NFS4Perm.EXECUTE |
    t.NFS4Perm.DELETE_CHILD | t.NFS4Perm.READ_ATTRIBUTES |
    t.NFS4Perm.WRITE_ATTRIBUTES | t.NFS4Perm.DELETE |
    t.NFS4Perm.READ_ACL | t.NFS4Perm.WRITE_ACL |
    t.NFS4Perm.WRITE_OWNER | t.NFS4Perm.SYNCHRONIZE
)

# Permissions tested under DENY (blocking op despite everyone@ FULL_CONTROL).
# FULL_DELETE is synthetic: denies both DELETE on file and DELETE_CHILD on dir.
DENY_PERMS = [
    'EXECUTE',
    'READ_DATA',
    'WRITE_DATA',
    'WRITE_ATTRIBUTES',
    'DELETE',
    'DELETE_CHILD',
    'FULL_DELETE',
    'READ_ACL',
    'WRITE_ACL',
    'WRITE_OWNER',
]

# Permissions tested under ALLOW / OMIT (no everyone@ baseline).
ALLOW_PERMS = [
    'EXECUTE',
    'READ_DATA',
    'WRITE_DATA',
    'WRITE_ATTRIBUTES',
    'DELETE',
    'DELETE_CHILD',
    'READ_ACL',
    'WRITE_ACL',
    'WRITE_OWNER',
]

# POSIX mode bits grouped by who they apply to
OWNER_BITS = {
    'OWNER_READ':    stat.S_IRUSR,
    'OWNER_WRITE':   stat.S_IWUSR,
    'OWNER_EXECUTE': stat.S_IXUSR,
}
GROUP_BITS = {
    'GROUP_READ':    stat.S_IRGRP,
    'GROUP_WRITE':   stat.S_IWGRP,
    'GROUP_EXECUTE': stat.S_IXGRP,
}
OTHER_BITS = {
    'OTHER_READ':    stat.S_IROTH,
    'OTHER_WRITE':   stat.S_IWOTH,
    'OTHER_EXECUTE': stat.S_IXOTH,
}
ALL_BITS = {**OWNER_BITS, **GROUP_BITS, **OTHER_BITS}

# Full rwx mask per category
_CATEGORY_RWX = {
    'OWNER': stat.S_IRWXU,
    'GROUP': stat.S_IRWXG,
    'OTHER': stat.S_IRWXO,
}
# Single execute bit per category (for "traverse only" parent directory)
_CATEGORY_EXEC = {
    'OWNER': stat.S_IXUSR,
    'GROUP': stat.S_IXGRP,
    'OTHER': stat.S_IXOTH,
}
# Single write+execute per category (for directory write tests)
_CATEGORY_WRITE_EXEC = {
    'OWNER': stat.S_IWUSR | stat.S_IXUSR,
    'GROUP': stat.S_IWGRP | stat.S_IXGRP,
    'OTHER': stat.S_IWOTH | stat.S_IXOTH,
}


# ── Shared helpers ────────────────────────────────────────────────────────────

@contextmanager
def run_as_user(username):
    """
    Temporarily assume the identity of `username` (uid, gid, supplementary
    groups), then restore.  Must be called as root.
    """
    orig_euid = os.geteuid()
    orig_egid = os.getegid()
    orig_groups = os.getgroups()
    pw = pwd.getpwnam(username)
    try:
        os.setgroups([])
        os.initgroups(pw.pw_name, pw.pw_gid)
        os.setegid(pw.pw_gid)
        os.seteuid(pw.pw_uid)
        yield pw
    finally:
        os.seteuid(orig_euid)
        os.setegid(orig_egid)
        os.setgroups(orig_groups)


def _fsetacl(path, aces, is_dir=False):
    """Set an NFS4 ACL on path from a list of NFS4Ace objects."""
    acl = t.NFS4ACL.from_aces(aces)
    oflags = os.O_RDONLY | (os.O_DIRECTORY if is_dir else 0)
    fd = os.open(path, oflags)
    try:
        t.fsetacl(fd, acl)
    finally:
        os.close(fd)


def _allow(who_type, mask, who_id=-1, ace_flags=None):
    return t.NFS4Ace(
        t.NFS4AceType.ALLOW,
        ace_flags if ace_flags is not None else t.NFS4Flag(0),
        mask, who_type, who_id,
    )


def _deny(who_type, mask, who_id=-1, ace_flags=None):
    return t.NFS4Ace(
        t.NFS4AceType.DENY,
        ace_flags if ace_flags is not None else t.NFS4Flag(0),
        mask, who_type, who_id,
    )


def _full_allow_all():
    """Full control for owner@, group@, everyone@."""
    return [
        _allow(t.NFS4Who.OWNER,    _NFS4_FULL),
        _allow(t.NFS4Who.GROUP,    _NFS4_FULL,
               ace_flags=t.NFS4Flag.IDENTIFIER_GROUP),
        _allow(t.NFS4Who.EVERYONE, _NFS4_FULL),
    ]


def _owner_group_only():
    """Full control for owner@ and group@ only (no everyone@)."""
    return [
        _allow(t.NFS4Who.OWNER, _NFS4_FULL),
        _allow(t.NFS4Who.GROUP, _NFS4_FULL,
               ace_flags=t.NFS4Flag.IDENTIFIER_GROUP),
    ]


# ── Module-scoped fixtures ────────────────────────────────────────────────────

@pytest.fixture(scope='module')
def local_user():
    """Create a non-privileged test user; delete it on teardown."""
    with Client() as c:
        usr = c.call('user.create', {
            'username':        'acl_test_user',
            'full_name':       'ACL Test User',
            'random_password': True,
            'group_create':    True,
        })
        try:
            yield usr
        finally:
            c.call('user.delete', usr['id'])


@pytest.fixture(scope='module')
def nfs4_dataset():
    """ZFS dataset with acltype=nfsv4 mounted under /var."""
    with Client() as c:
        mnt = c.call(
            'filesystem.mount_info',
            [['mountpoint', '=', '/var']], {'get': True},
        )

    lz = truenas_pylibzfs.open_handle()
    ds_name = f'{mnt["mount_source"]}/acl_enforce_nfs4'
    lz.create_resource(
        name=ds_name,
        type=truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM,
        properties={
            truenas_pylibzfs.ZFSProperty.ACLTYPE: 'nfsv4',
            truenas_pylibzfs.ZFSProperty.ACLMODE: 'passthrough',
        },
    )
    rsrc = lz.open_resource(name=ds_name)
    try:
        rsrc.mount()
        yield rsrc.properties[truenas_pylibzfs.ZFSProperty.MOUNTPOINT].value
    finally:
        rsrc.unmount()
        lz.destroy_resource(name=ds_name)


# ── Per-test NFS4 environment ─────────────────────────────────────────────────

def _write_testfile(filepath):
    with open(filepath, 'w') as f:
        f.write('#!/bin/sh\necho CANARY\n')
    os.chmod(filepath, 0o755)
    os.chown(filepath, 0, 0)


@pytest.fixture(scope='function')
def nfs4_env(nfs4_dataset):
    """
    Fresh test directory + script file owned by root with full-access NFS4 ACL.
    Yields (dirpath, filepath).
    """
    dirpath = os.path.join(nfs4_dataset, 'testdir')
    filepath = os.path.join(dirpath, 'testfile.sh')
    os.mkdir(dirpath)
    _write_testfile(filepath)
    os.chown(dirpath, 0, 0)
    _fsetacl(dirpath,  _full_allow_all(), is_dir=True)
    _fsetacl(filepath, _full_allow_all(), is_dir=False)
    try:
        yield dirpath, filepath
    finally:
        shutil.rmtree(dirpath, ignore_errors=True)


# ── NFS4 ACL setup helpers ────────────────────────────────────────────────────

def _apply_deny_acl(dirpath, filepath, uid, perm):
    """
    Prepend a DENY ACE for uid on the relevant target(s), backed by
    FULL_CONTROL for owner@/group@/everyone@.
    """
    if perm == 'EXECUTE':
        _fsetacl(dirpath,
                 [_deny(t.NFS4Who.NAMED, t.NFS4Perm.EXECUTE, uid)]
                 + _full_allow_all(), is_dir=True)
        _fsetacl(filepath, _full_allow_all(), is_dir=False)

    elif perm == 'DELETE_CHILD':
        # Deny DELETE_CHILD on dir; DELETE on the file remains ALLOWED.
        # On Linux deletion still succeeds per RFC 5661 § 6.2.1.3.2.
        _fsetacl(dirpath,
                 [_deny(t.NFS4Who.NAMED, t.NFS4Perm.DELETE_CHILD, uid)]
                 + _full_allow_all(), is_dir=True)
        _fsetacl(filepath, _full_allow_all(), is_dir=False)

    elif perm == 'FULL_DELETE':
        # Deny both DELETE on file and DELETE_CHILD on dir.
        _fsetacl(dirpath,
                 [_deny(t.NFS4Who.NAMED, t.NFS4Perm.DELETE_CHILD, uid)]
                 + _full_allow_all(), is_dir=True)
        _fsetacl(filepath,
                 [_deny(t.NFS4Who.NAMED, t.NFS4Perm.DELETE, uid)]
                 + _full_allow_all(), is_dir=False)

    else:
        mask = getattr(t.NFS4Perm, perm)
        _fsetacl(dirpath, _full_allow_all(), is_dir=True)
        _fsetacl(filepath,
                 [_deny(t.NFS4Who.NAMED, mask, uid)]
                 + _full_allow_all(), is_dir=False)


def _apply_allow_acl(dirpath, filepath, uid, perm):
    """
    Grant uid the specific perm (plus required supporting perms) via an ALLOW
    ACE prepended to owner@/group@-only baseline (no everyone@).
    """
    support = t.NFS4Perm.EXECUTE | t.NFS4Perm.READ_ATTRIBUTES

    if perm == 'EXECUTE':
        dir_mask = t.NFS4Perm.EXECUTE | t.NFS4Perm.READ_ATTRIBUTES
        file_mask = t.NFS4Perm.READ_ATTRIBUTES
    elif perm == 'DELETE_CHILD':
        dir_mask = t.NFS4Perm.DELETE_CHILD | support
        file_mask = t.NFS4Perm.READ_ATTRIBUTES
    elif perm == 'WRITE_ACL':
        dir_mask = support
        file_mask = t.NFS4Perm.WRITE_ACL | t.NFS4Perm.READ_ACL | support
    else:
        dir_mask = support
        file_mask = getattr(t.NFS4Perm, perm) | support

    _fsetacl(dirpath,
             [_allow(t.NFS4Who.NAMED, dir_mask, uid)]
             + _owner_group_only(), is_dir=True)
    _fsetacl(filepath,
             [_allow(t.NFS4Who.NAMED, file_mask, uid)]
             + _owner_group_only(), is_dir=False)


def _apply_omit_acl(dirpath, filepath, uid, perm):
    """
    Like _apply_allow_acl but WITHOUT the perm under test; supporting perms
    only.  The operation should fail.
    """
    support = t.NFS4Perm.EXECUTE | t.NFS4Perm.READ_ATTRIBUTES

    if perm == 'EXECUTE':
        dir_mask = t.NFS4Perm.READ_ATTRIBUTES   # EXECUTE omitted
        file_mask = t.NFS4Perm.READ_ATTRIBUTES
    elif perm == 'DELETE_CHILD':
        dir_mask = support                        # DELETE_CHILD omitted
        file_mask = t.NFS4Perm.READ_ATTRIBUTES
    elif perm == 'WRITE_ACL':
        dir_mask = support
        file_mask = t.NFS4Perm.READ_ACL | support  # WRITE_ACL omitted
    else:
        dir_mask = support
        file_mask = support                         # specific perm omitted

    _fsetacl(dirpath,
             [_allow(t.NFS4Who.NAMED, dir_mask, uid)]
             + _owner_group_only(), is_dir=True)
    _fsetacl(filepath,
             [_allow(t.NFS4Who.NAMED, file_mask, uid)]
             + _owner_group_only(), is_dir=False)


# ── NFS4 operation helper ─────────────────────────────────────────────────────

def _do_nfs4_op(perm, dirpath, filepath, username, uid, acl_bytes=None):
    """
    Attempt the filesystem operation that exercises `perm` as `username`.
    Returns True on success, False on PermissionError.
    acl_bytes must be pre-read (as root) when perm == 'WRITE_ACL'.
    """
    try:
        with run_as_user(username) as pw:
            if perm == 'EXECUTE':
                # Traverse the directory to reach the file
                os.stat(filepath)

            elif perm == 'READ_DATA':
                open(filepath).read()

            elif perm == 'WRITE_DATA':
                with open(filepath, 'a') as f:
                    f.write('x')

            elif perm == 'WRITE_ATTRIBUTES':
                os.utime(filepath, (0, 0))

            elif perm in ('DELETE', 'DELETE_CHILD', 'FULL_DELETE'):
                os.unlink(filepath)

            elif perm == 'READ_ACL':
                os.getxattr(filepath, 'system.nfs4_acl_xdr')

            elif perm == 'WRITE_ACL':
                os.setxattr(filepath, 'system.nfs4_acl_xdr', acl_bytes)

            elif perm == 'WRITE_OWNER':
                os.chown(filepath, pw.pw_uid, -1)

        return True
    except PermissionError:
        return False


# ── NFS4 deny tests ───────────────────────────────────────────────────────────

@pytest.mark.parametrize('perm', DENY_PERMS)
def test_nfs4_deny(local_user, nfs4_env, perm):
    """
    Prepend a DENY ACE for the test user blocking a specific permission.
    Despite a blanket ALLOW from everyone@, the operation must fail.

    Exception: DENY DELETE_CHILD alone on Linux does NOT block deletion
    when DELETE on the file is still ALLOWED (RFC 5661 § 6.2.1.3.2 as
    implemented by the Linux NFS4 ACL layer).
    """
    dirpath, filepath = nfs4_env
    uid = local_user['uid']
    username = local_user['username']

    # Read ACL bytes as root before switching identity (needed for WRITE_ACL)
    acl_bytes = (os.getxattr(filepath, 'system.nfs4_acl_xdr')
                 if perm == 'WRITE_ACL' else None)

    _apply_deny_acl(dirpath, filepath, uid, perm)
    succeeded = _do_nfs4_op(perm, dirpath, filepath, username, uid, acl_bytes)

    if perm == 'DELETE_CHILD':
        # DELETE on the file is still ALLOWED, so deletion succeeds on Linux
        assert succeeded, (
            'DENY DELETE_CHILD alone should not block deletion: '
            'DELETE on file is still ALLOWED'
        )
        _write_testfile(filepath)
        _fsetacl(filepath, _full_allow_all(), is_dir=False)
    else:
        assert not succeeded, f'DENY {perm} should have blocked the operation'


# ── NFS4 allow tests ──────────────────────────────────────────────────────────

@pytest.mark.parametrize('perm', ALLOW_PERMS)
def test_nfs4_allow(local_user, nfs4_env, perm):
    """
    Grant the test user only the specific permission (plus required supporting
    perms).  With no everyone@ in the baseline, access hinges solely on the
    ALLOW ACE; the operation must succeed.
    """
    dirpath, filepath = nfs4_env
    uid = local_user['uid']
    username = local_user['username']

    acl_bytes = (os.getxattr(filepath, 'system.nfs4_acl_xdr')
                 if perm == 'WRITE_ACL' else None)

    _apply_allow_acl(dirpath, filepath, uid, perm)
    succeeded = _do_nfs4_op(perm, dirpath, filepath, username, uid, acl_bytes)

    assert succeeded, f'ALLOW {perm} should have permitted the operation'

    if perm in ('DELETE', 'DELETE_CHILD') and not os.path.exists(filepath):
        _write_testfile(filepath)
        _apply_allow_acl(dirpath, filepath, uid, perm)


# ── NFS4 omit tests ───────────────────────────────────────────────────────────

@pytest.mark.parametrize('perm', ALLOW_PERMS)
def test_nfs4_omit(local_user, nfs4_env, perm):
    """
    Grant the test user the supporting perms but omit the permission under
    test.  The operation must fail.
    """
    dirpath, filepath = nfs4_env
    uid = local_user['uid']
    username = local_user['username']

    acl_bytes = (os.getxattr(filepath, 'system.nfs4_acl_xdr')
                 if perm == 'WRITE_ACL' else None)

    _apply_omit_acl(dirpath, filepath, uid, perm)
    succeeded = _do_nfs4_op(perm, dirpath, filepath, username, uid, acl_bytes)

    assert not succeeded, f'Omitting {perm} should have blocked the operation'


# ── NFS4 file-execute specific tests ─────────────────────────────────────────
# These mirror test_26 / test_27 / test_28 from the deleted test_345_acl_nfs4.py.
# They test EXECUTE on the file itself (script execution) rather than directory
# traverse, which is already covered by the parametrised EXECUTE cases above.

def _exec_as_user(filepath, username):
    """
    Run filepath as username.  Returns True if the process exited 0,
    False if exec was denied (PermissionError) or the process failed.
    """
    try:
        with run_as_user(username):
            result = subprocess.run(
                [filepath], capture_output=True, timeout=5,
            )
        return result.returncode == 0
    except PermissionError:
        return False


def test_nfs4_file_execute_deny(local_user, nfs4_env):
    """
    DENY EXECUTE (FILE_INHERIT) blocks script execution even though the
    directory-level ALLOW grants traverse.  The file has FULL_CONTROL from
    everyone@ but the user-specific DENY takes precedence.
    """
    dirpath, filepath = nfs4_env
    uid = local_user['uid']
    username = local_user['username']

    fi = t.NFS4Flag.FILE_INHERIT

    # Directory: user can traverse (ALLOW EXECUTE, no FILE_INHERIT) and
    # the everyone@ FULL_CONTROL covers everything else.
    dir_aces = [
        _deny(t.NFS4Who.NAMED, t.NFS4Perm.EXECUTE, uid, ace_flags=fi),
        _allow(t.NFS4Who.NAMED, t.NFS4Perm.EXECUTE, uid),
    ] + _full_allow_all()
    _fsetacl(dirpath, dir_aces, is_dir=True)

    # File: inherited DENY EXECUTE for the user; everyone@ still FULL_CONTROL.
    inh = t.NFS4Flag.INHERITED
    file_aces = [
        _deny(t.NFS4Who.NAMED, t.NFS4Perm.EXECUTE, uid, ace_flags=inh),
    ] + _full_allow_all()
    _fsetacl(filepath, file_aces, is_dir=False)

    assert not _exec_as_user(filepath, username), (
        'DENY EXECUTE on file should prevent script execution'
    )


def test_nfs4_file_execute_allow(local_user, nfs4_env):
    """
    ALLOW EXECUTE + READ_DATA + READ_ATTRIBUTES (FILE_INHERIT) permits script
    execution.  No everyone@ in baseline so the ALLOW ACE is the sole grant.
    """
    dirpath, filepath = nfs4_env
    uid = local_user['uid']
    username = local_user['username']

    fi = t.NFS4Flag.FILE_INHERIT
    inh = t.NFS4Flag.INHERITED
    exec_mask = (t.NFS4Perm.EXECUTE | t.NFS4Perm.READ_DATA |
                 t.NFS4Perm.READ_ATTRIBUTES)

    dir_aces = [
        _allow(t.NFS4Who.NAMED, exec_mask, uid, ace_flags=fi),
        _allow(t.NFS4Who.NAMED, t.NFS4Perm.EXECUTE, uid),
    ] + _owner_group_only()
    _fsetacl(dirpath, dir_aces, is_dir=True)

    file_aces = [
        _allow(t.NFS4Who.NAMED, exec_mask, uid, ace_flags=inh),
    ] + _owner_group_only()
    _fsetacl(filepath, file_aces, is_dir=False)

    assert _exec_as_user(filepath, username), (
        'ALLOW EXECUTE+READ_DATA+READ_ATTRIBUTES should permit script execution'
    )


def test_nfs4_file_execute_omit(local_user, nfs4_env):
    """
    Granting all NFS4 perms EXCEPT EXECUTE on the file prevents execution
    even though the user can traverse the directory.
    """
    dirpath, filepath = nfs4_env
    uid = local_user['uid']
    username = local_user['username']

    fi = t.NFS4Flag.FILE_INHERIT
    inh = t.NFS4Flag.INHERITED
    no_exec = _NFS4_FULL & ~t.NFS4Perm.EXECUTE

    dir_aces = [
        _allow(t.NFS4Who.NAMED, no_exec, uid, ace_flags=fi),
        _allow(t.NFS4Who.NAMED, t.NFS4Perm.EXECUTE, uid),
    ] + _owner_group_only()
    _fsetacl(dirpath, dir_aces, is_dir=True)

    file_aces = [
        _allow(t.NFS4Who.NAMED, no_exec, uid, ace_flags=inh),
    ] + _owner_group_only()
    _fsetacl(filepath, file_aces, is_dir=False)

    assert not _exec_as_user(filepath, username), (
        'Omitting EXECUTE from file ACE should prevent script execution'
    )


# ── POSIX mode bit tests ──────────────────────────────────────────────────────

@pytest.fixture(scope='function')
def posix_env(local_user):
    """
    Temporary directory (base/testdir/) with a canary shell script inside.
    Everything starts at 0o777 so tests can set exactly the permissions they
    need.  Yields (dirpath, testfile).
    """
    base = tempfile.mkdtemp(prefix='acl_mode_test_')
    dirpath = os.path.join(base, 'testdir')
    os.makedirs(dirpath)

    testfile = os.path.join(dirpath, 'canary.sh')
    with open(testfile, 'w') as f:
        f.write('#!/bin/sh\necho CANARY\n')

    os.chmod(base,    0o777)
    os.chmod(dirpath, 0o777)
    os.chmod(testfile, 0o777)

    try:
        yield dirpath, testfile
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _chown_for(path, category, local_user):
    """
    Set ownership so the test user falls into the right category:
      OWNER → test user is owner
      GROUP → test user's primary group is file's group, root is owner
      OTHER → root owns file in root's group; test user is neither
    """
    uid = local_user['uid']
    gid = pwd.getpwnam(local_user['username']).pw_gid

    if category == 'OWNER':
        os.chown(path, uid, 0)
    elif category == 'GROUP':
        os.chown(path, 0, gid)
    else:
        os.chown(path, 0, 0)


def _category(mode_bit_name):
    if mode_bit_name.startswith('OWNER'):
        return 'OWNER'
    if mode_bit_name.startswith('GROUP'):
        return 'GROUP'
    return 'OTHER'


# ── Directory mode bit tests ──────────────────────────────────────────────────

@pytest.mark.parametrize('mode_bit', list(ALL_BITS))
def test_posix_dir_mode_bit(local_user, posix_env, mode_bit):
    """
    Set a single mode bit (or WRITE+EXECUTE for write tests) on a directory
    and verify kernel enforcement:

    READ    → listing succeeds; creating a file and traversal both fail.
    WRITE   → listing fails; creating and deleting a file succeed
              (EXECUTE added alongside WRITE since write alone is useless).
    EXECUTE → listing fails; creating a file fails.
    """
    dirpath, testfile = posix_env
    username = local_user['username']
    cat = _category(mode_bit)
    bit = ALL_BITS[mode_bit]

    mode = _CATEGORY_WRITE_EXEC[cat] if mode_bit.endswith('WRITE') else bit

    _chown_for(dirpath, cat, local_user)
    os.chmod(dirpath, mode)

    newfile = os.path.join(dirpath, 'newfile')

    with run_as_user(username):
        if mode_bit.endswith('READ'):
            # Can list
            os.listdir(dirpath)

            # Can't create (no WRITE)
            with pytest.raises(PermissionError):
                open(newfile, 'w').close()

            # Can't traverse (no EXECUTE) — stat a known file inside
            with pytest.raises(PermissionError):
                os.stat(testfile)

        elif mode_bit.endswith('WRITE'):
            # Can't list (no READ)
            with pytest.raises(PermissionError):
                os.listdir(dirpath)

            # Can create and delete (WRITE + EXECUTE)
            open(newfile, 'w').close()
            os.unlink(newfile)

        else:  # EXECUTE
            # Can't list (no READ)
            with pytest.raises(PermissionError):
                os.listdir(dirpath)

            # Can't create (no WRITE)
            with pytest.raises(PermissionError):
                open(newfile, 'w').close()


# ── File mode bit tests ───────────────────────────────────────────────────────

@pytest.mark.parametrize('mode_bit', list(ALL_BITS))
def test_posix_file_mode_bit(local_user, posix_env, mode_bit):
    """
    Set a single mode bit on a file and verify kernel enforcement.
    The parent directory is set to traverse-only for the test user.

    READ    → reading succeeds; writing and executing fail.
    WRITE   → writing succeeds; reading, executing, and deleting fail
              (parent has no WRITE so unlink is denied).
    EXECUTE → reading and writing fail; execution fails too (shell scripts
              also need READ to read the script body, so this confirms the
              kernel denies the exec syscall when only EXECUTE is set without
              READ — the shell exits non-zero, not PermissionError on exec).
    """
    dirpath, testfile = posix_env
    username = local_user['username']
    cat = _category(mode_bit)
    bit = ALL_BITS[mode_bit]

    # Parent: traverse-only for the test user's category
    _chown_for(dirpath, cat, local_user)
    os.chmod(dirpath, _CATEGORY_EXEC[cat])

    _chown_for(testfile, cat, local_user)
    os.chmod(testfile, bit)

    with run_as_user(username):
        if mode_bit.endswith('READ'):
            # Can read
            open(testfile).read()

            # Can't write
            with pytest.raises(PermissionError):
                open(testfile, 'w').write('x')

            # Can't execute (no EXECUTE bit)
            with pytest.raises(PermissionError):
                subprocess.run([testfile], check=True,
                               capture_output=True, timeout=5)

        elif mode_bit.endswith('WRITE'):
            # Can't read
            with pytest.raises(PermissionError):
                open(testfile).read()

            # Can write (O_WRONLY does not need READ)
            with open(testfile, 'w') as f:
                f.write('x')

            # Can't execute (no EXECUTE bit)
            with pytest.raises(PermissionError):
                subprocess.run([testfile], check=True,
                               capture_output=True, timeout=5)

            # Can't delete — parent directory has only EXECUTE, not WRITE
            with pytest.raises(PermissionError):
                os.unlink(testfile)

        else:  # EXECUTE
            # Can't read (no READ bit)
            with pytest.raises(PermissionError):
                open(testfile).read()

            # Can't write (no WRITE bit)
            with pytest.raises(PermissionError):
                open(testfile, 'w').write('x')

            # Exec syscall is permitted by the kernel (EXECUTE is set), but
            # the shell cannot read the script body, so it exits non-zero.
            result = subprocess.run([testfile], capture_output=True, timeout=5)
            assert result.returncode != 0, (
                'script should fail: shell cannot read body without READ bit'
            )


@pytest.mark.parametrize('mode_bit', list(ALL_BITS))
def test_posix_file_mode_bit_xor(local_user, posix_env, mode_bit):
    """
    Set all mode bits EXCEPT the one under test and verify that the
    missing bit's operation fails.  Parent directory gives full access so
    the only restriction is on the file itself.
    """
    dirpath, testfile = posix_env
    username = local_user['username']
    cat = _category(mode_bit)
    bit = ALL_BITS[mode_bit]
    xor_mode = _CATEGORY_RWX[cat] ^ bit

    _chown_for(dirpath, cat, local_user)
    os.chmod(dirpath, _CATEGORY_RWX[cat])

    _chown_for(testfile, cat, local_user)
    os.chmod(testfile, xor_mode)

    with run_as_user(username):
        if mode_bit.endswith('READ'):
            with pytest.raises(PermissionError):
                open(testfile).read()

        elif mode_bit.endswith('WRITE'):
            with pytest.raises(PermissionError):
                open(testfile, 'w').write('x')

        else:  # EXECUTE
            with pytest.raises(PermissionError):
                subprocess.run([testfile], check=True,
                               capture_output=True, timeout=5)
