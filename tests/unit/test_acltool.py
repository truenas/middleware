"""
Comprehensive live tests for acltool() in middlewared.plugins.filesystem_.utils.

Tests run on a TrueNAS system and create real ZFS datasets.  Coverage:

  POSIX1E (no traverse)
    - No ValueError raised when root dir has default ACL entries (regression)
    - Files receive no default ACL entries
    - Directories retain default ACL entries
    - Files receive access ACL entries

  POSIX1E (traverse=True, child dataset)
    - Same invariants hold across the child dataset mount

  NFS4 (no traverse)
    - Files and directories receive NFS4 ACLs with access entries

  NFS4 (traverse=True, child dataset)
    - Same invariants hold across the child dataset mount

Both CLONE and INHERIT actions are parametrised for each group.
"""

import errno
import os
import shutil
import stat

import pytest
import truenas_os as t
import truenas_pylibzfs
from truenas_api_client import Client

from middlewared.plugins.filesystem_.utils import AclTool, AclToolAction, ATAclOptions, ATPermOptions
from middlewared.utils.filesystem.acl import ACL_UNDEFINED_ID


# ---------------------------------------------------------------------------
# NFS4 constants
# ---------------------------------------------------------------------------

_NFS4_FULL = (
    t.NFS4Perm.READ_DATA | t.NFS4Perm.WRITE_DATA | t.NFS4Perm.APPEND_DATA |
    t.NFS4Perm.READ_NAMED_ATTRS | t.NFS4Perm.WRITE_NAMED_ATTRS |
    t.NFS4Perm.EXECUTE | t.NFS4Perm.DELETE_CHILD | t.NFS4Perm.READ_ATTRIBUTES |
    t.NFS4Perm.WRITE_ATTRIBUTES | t.NFS4Perm.DELETE | t.NFS4Perm.READ_ACL |
    t.NFS4Perm.WRITE_ACL | t.NFS4Perm.WRITE_OWNER | t.NFS4Perm.SYNCHRONIZE
)
_INHERIT = t.NFS4Flag.FILE_INHERIT | t.NFS4Flag.DIRECTORY_INHERIT

_CLONE_INHERIT = [AclToolAction.CLONE, AclToolAction.INHERIT]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_fd(path, is_dir=False):
    return os.open(path, os.O_RDONLY | (os.O_DIRECTORY if is_dir else 0))


def _get_acl(path, is_dir=False):
    fd = _open_fd(path, is_dir=is_dir)
    try:
        return t.fgetacl(fd)
    finally:
        os.close(fd)


def _set_posix_acl(path, is_dir):
    """Write a POSIXACL with access entries; add default entries on dirs."""
    rwx = t.POSIXPerm.READ | t.POSIXPerm.WRITE | t.POSIXPerm.EXECUTE
    aces = [
        t.POSIXAce(t.POSIXTag.USER_OBJ,  rwx,             default=False),
        t.POSIXAce(t.POSIXTag.GROUP_OBJ, rwx,             default=False),
        t.POSIXAce(t.POSIXTag.OTHER,     t.POSIXPerm(0),  default=False),
    ]
    if is_dir:
        aces += [
            t.POSIXAce(t.POSIXTag.USER_OBJ,  rwx,             default=True),
            t.POSIXAce(t.POSIXTag.GROUP_OBJ, rwx,             default=True),
            t.POSIXAce(t.POSIXTag.OTHER,     t.POSIXPerm(0),  default=True),
        ]
    fd = _open_fd(path, is_dir=is_dir)
    try:
        t.fsetacl(fd, t.POSIXACL.from_aces(aces))
    finally:
        os.close(fd)


def _set_nfs4_acl(path, is_dir):
    """Write an NFS4ACL with full-control inheritable ACEs on dirs."""
    inh = _INHERIT if is_dir else t.NFS4Flag(0)
    aces = [
        t.NFS4Ace(t.NFS4AceType.ALLOW, inh,
                  _NFS4_FULL, t.NFS4Who.OWNER),
        t.NFS4Ace(t.NFS4AceType.ALLOW, inh | t.NFS4Flag.IDENTIFIER_GROUP,
                  _NFS4_FULL, t.NFS4Who.GROUP),
        t.NFS4Ace(t.NFS4AceType.ALLOW, inh,
                  _NFS4_FULL, t.NFS4Who.EVERYONE),
    ]
    fd = _open_fd(path, is_dir=is_dir)
    try:
        t.fsetacl(fd, t.NFS4ACL.from_aces(aces))
    finally:
        os.close(fd)


def _run_acltool(root_path, action, traverse=False):
    fd = t.openat2(root_path, flags=os.O_RDONLY, resolve=t.RESOLVE_NO_SYMLINKS)
    try:
        root_acl = t.fgetacl(fd)
        AclTool(fd, action, ACL_UNDEFINED_ID, ACL_UNDEFINED_ID,
                ATAclOptions(target_acl=root_acl, traverse=traverse)).run()
    finally:
        os.close(fd)


def _make_tree(root):
    """
    Build:
        root/
            file.txt
            subdir/
                file.txt
    Returns (root, subdir, file_root, file_sub).
    """
    subdir = os.path.join(root, 'subdir')
    file_root = os.path.join(root, 'file.txt')
    file_sub = os.path.join(subdir, 'file.txt')
    os.makedirs(subdir)
    for path in (file_root, file_sub):
        with open(path, 'w') as fh:
            fh.write('test\n')
    return root, subdir, file_root, file_sub


def _pool_ds():
    """Return the pool/dataset that backs /var (used as parent for test datasets)."""
    with Client() as c:
        return c.call('filesystem.mount_info', [['mountpoint', '=', '/var']], {'get': True})['mount_source']


# ---------------------------------------------------------------------------
# Module-scoped dataset fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def posix_dataset():
    """POSIX1E dataset under /var; yields (mountpoint, ds_name)."""
    ds_name = f'{_pool_ds()}/acltool_posix'
    lz = truenas_pylibzfs.open_handle()
    lz.create_resource(
        name=ds_name,
        type=truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM,
        properties={
            truenas_pylibzfs.ZFSProperty.ACLTYPE: 'posix',
            truenas_pylibzfs.ZFSProperty.ACLMODE: 'passthrough',
        },
    )
    rsrc = lz.open_resource(name=ds_name)
    try:
        rsrc.mount()
        yield rsrc.get_mountpoint(), ds_name
    finally:
        rsrc.unmount()
        lz.destroy_resource(name=ds_name)


@pytest.fixture(scope='module')
def nfs4_dataset():
    """NFS4 dataset under /var; yields (mountpoint, ds_name)."""
    ds_name = f'{_pool_ds()}/acltool_nfs4'
    lz = truenas_pylibzfs.open_handle()
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
        yield rsrc.get_mountpoint(), ds_name
    finally:
        rsrc.unmount()
        lz.destroy_resource(name=ds_name)


@pytest.fixture(scope='module')
def nfs4_restricted_dataset():
    """NFS4 dataset with aclmode=restricted; yields (mountpoint, ds_name).

    On aclmode=restricted fchmod() raises EPERM when a non-trivial ACL is
    present.  Any accidental chmod during a CLONE pass will therefore blow up
    immediately, making this fixture a self-enforcing correctness check.
    """
    ds_name = f'{_pool_ds()}/acltool_nfs4_restricted'
    lz = truenas_pylibzfs.open_handle()
    lz.create_resource(
        name=ds_name,
        type=truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM,
        properties={
            truenas_pylibzfs.ZFSProperty.ACLTYPE: 'nfsv4',
            truenas_pylibzfs.ZFSProperty.ACLMODE: 'restricted',
        },
    )
    rsrc = lz.open_resource(name=ds_name)
    try:
        rsrc.mount()
        yield rsrc.get_mountpoint(), ds_name
    finally:
        rsrc.unmount()
        lz.destroy_resource(name=ds_name)


# ---------------------------------------------------------------------------
# Function-scoped test environment fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='function')
def posix_env(posix_dataset):
    """Fresh POSIX tree with default ACL set on root."""
    mnt, _ = posix_dataset
    root = os.path.join(mnt, 'testroot')
    env = _make_tree(root)
    _set_posix_acl(root, is_dir=True)
    try:
        yield env
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(scope='function')
def nfs4_env(nfs4_dataset):
    """Fresh NFS4 tree with inheritable ACL set on root."""
    mnt, _ = nfs4_dataset
    root = os.path.join(mnt, 'testroot')
    env = _make_tree(root)
    _set_nfs4_acl(root, is_dir=True)
    try:
        yield env
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(scope='function')
def nfs4_restricted_env(nfs4_restricted_dataset):
    """Fresh NFS4/restricted tree with non-trivial ACL set on every node.

    The non-trivial ACL is set on both the root *and* all children so that
    fchmod() on any child will fail with EPERM — which is exactly what makes
    this fixture a useful regression guard for spurious do_chmod behaviour.
    """
    mnt, _ = nfs4_restricted_dataset
    root = os.path.join(mnt, 'testroot')
    env = _make_tree(root)
    root, subdir, file_root, file_sub = env
    _set_nfs4_acl(root, is_dir=True)
    _set_nfs4_acl(subdir, is_dir=True)
    _set_nfs4_acl(file_root, is_dir=False)
    _set_nfs4_acl(file_sub, is_dir=False)
    try:
        yield env
    finally:
        # Strip ACLs first so rmtree's unlink/rmdir calls are not blocked by
        # restricted aclmode preventing the implicit chmod(0) that some
        # libc rmtree implementations perform.
        for path, is_dir in (
            (file_sub, False), (file_root, False),
            (subdir, True), (root, True),
        ):
            try:
                _strip_acl(path)
            except Exception:
                pass
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(scope='function')
def posix_traverse_env(posix_dataset):
    """
    POSIX tree rooted at the parent dataset mountpoint with a child dataset
    mounted naturally inside it.

    The acltool root is the parent dataset mountpoint directly so that the
    child dataset (which ZFS mounts at <parent_mnt>/child) falls under the
    root and is therefore reached by traverse=True.

    Tree layout:
        <parent_mnt>/               ← acltool root
            file.txt
            subdir/
                file.txt
            child/                  ← child ZFS dataset mountpoint
                childfile.txt
                childsubdir/
                    childfile.txt

    Yields (root, subdir, file_root, file_sub,
            child_mnt, child_subdir, child_file_root, child_file_sub).
    """
    parent_mnt, parent_ds = posix_dataset

    subdir = os.path.join(parent_mnt, 'subdir')
    file_root = os.path.join(parent_mnt, 'file.txt')
    file_sub = os.path.join(subdir, 'file.txt')
    os.makedirs(subdir)
    for path in (file_root, file_sub):
        with open(path, 'w') as fh:
            fh.write('test\n')

    child_ds_name = f'{parent_ds}/child'
    lz = truenas_pylibzfs.open_handle()
    lz.create_resource(
        name=child_ds_name,
        type=truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM,
        properties={
            truenas_pylibzfs.ZFSProperty.ACLTYPE: 'posix',
            truenas_pylibzfs.ZFSProperty.ACLMODE: 'passthrough',
        },
    )
    child_rsrc = lz.open_resource(name=child_ds_name)
    child_rsrc.mount()
    child_mnt = child_rsrc.get_mountpoint()

    child_subdir = os.path.join(child_mnt, 'childsubdir')
    child_file_root = os.path.join(child_mnt, 'childfile.txt')
    child_file_sub = os.path.join(child_subdir, 'childfile.txt')
    os.makedirs(child_subdir)
    for path in (child_file_root, child_file_sub):
        with open(path, 'w') as fh:
            fh.write('child\n')

    _set_posix_acl(parent_mnt, is_dir=True)
    try:
        yield (parent_mnt, subdir, file_root, file_sub,
               child_mnt, child_subdir, child_file_root, child_file_sub)
    finally:
        child_rsrc.unmount()
        lz.destroy_resource(name=child_ds_name)
        for path in (subdir, file_root):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.unlink(path)
            except FileNotFoundError:
                pass


@pytest.fixture(scope='function')
def nfs4_traverse_env(nfs4_dataset):
    """
    NFS4 tree rooted at the parent dataset mountpoint with a child dataset
    mounted naturally inside it (same structure as posix_traverse_env).

    Yields (root, subdir, file_root, file_sub,
            child_mnt, child_subdir, child_file_root, child_file_sub).
    """
    parent_mnt, parent_ds = nfs4_dataset

    subdir = os.path.join(parent_mnt, 'subdir')
    file_root = os.path.join(parent_mnt, 'file.txt')
    file_sub = os.path.join(subdir, 'file.txt')
    os.makedirs(subdir)
    for path in (file_root, file_sub):
        with open(path, 'w') as fh:
            fh.write('test\n')

    child_ds_name = f'{parent_ds}/child'
    lz = truenas_pylibzfs.open_handle()
    lz.create_resource(
        name=child_ds_name,
        type=truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM,
        properties={
            truenas_pylibzfs.ZFSProperty.ACLTYPE: 'nfsv4',
            truenas_pylibzfs.ZFSProperty.ACLMODE: 'passthrough',
        },
    )
    child_rsrc = lz.open_resource(name=child_ds_name)
    child_rsrc.mount()
    child_mnt = child_rsrc.get_mountpoint()

    child_subdir = os.path.join(child_mnt, 'childsubdir')
    child_file_root = os.path.join(child_mnt, 'childfile.txt')
    child_file_sub = os.path.join(child_subdir, 'childfile.txt')
    os.makedirs(child_subdir)
    for path in (child_file_root, child_file_sub):
        with open(path, 'w') as fh:
            fh.write('child\n')

    _set_nfs4_acl(parent_mnt, is_dir=True)
    try:
        yield (parent_mnt, subdir, file_root, file_sub,
               child_mnt, child_subdir, child_file_root, child_file_sub)
    finally:
        child_rsrc.unmount()
        lz.destroy_resource(name=child_ds_name)
        for path in (subdir, file_root):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.unlink(path)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------------------
# POSIX tests (no traverse)
# ---------------------------------------------------------------------------

class TestAcltoolPosix:

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_no_error_on_files_with_default_acl(self, posix_env, action):
        """
        Regression: acltool() must not raise ValueError when the root
        directory carries a POSIX ACL with default entries and the tree
        contains regular files.

        Before the fix, fsetacl() was called with the full root POSIXACL
        (including default entries) on files, raising:
          ValueError: default ACL is only valid on directories
        """
        root, *_ = posix_env
        _run_acltool(root, action)

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_files_have_no_default_entries(self, posix_env, action):
        """Files must not receive default ACL entries after acltool()."""
        root, subdir, file_root, file_sub = posix_env
        _run_acltool(root, action)

        for path in (file_root, file_sub):
            acl = _get_acl(path)
            assert isinstance(acl, t.POSIXACL)
            assert not acl.default_aces, (
                f'{path}: file must not have default ACL entries '
                f'after acltool({action})'
            )

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_dirs_have_default_entries(self, posix_env, action):
        """Directories must retain default ACL entries after acltool()."""
        root, subdir, file_root, file_sub = posix_env
        _run_acltool(root, action)

        for path in (root, subdir):
            acl = _get_acl(path, is_dir=True)
            assert isinstance(acl, t.POSIXACL)
            assert acl.default_aces, (
                f'{path}: directory must have default ACL entries '
                f'after acltool({action})'
            )

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_files_have_access_entries(self, posix_env, action):
        """Files must still have access ACL entries after acltool()."""
        root, subdir, file_root, file_sub = posix_env
        _run_acltool(root, action)

        for path in (file_root, file_sub):
            acl = _get_acl(path)
            assert isinstance(acl, t.POSIXACL)
            assert acl.aces, (
                f'{path}: file must have access ACL entries '
                f'after acltool({action})'
            )


# ---------------------------------------------------------------------------
# POSIX tests (traverse=True)
# ---------------------------------------------------------------------------

class TestAcltoolPosixTraverse:

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_child_files_have_no_default_entries(self, posix_traverse_env, action):
        """Files in child dataset must not receive default ACL entries."""
        root, subdir, file_root, file_sub, \
            child_mnt, child_subdir, child_file_root, child_file_sub = posix_traverse_env

        _run_acltool(root, action, traverse=True)

        for path in (child_file_root, child_file_sub):
            acl = _get_acl(path)
            assert isinstance(acl, t.POSIXACL)
            assert not acl.default_aces, (
                f'{path}: child file must not have default ACL entries '
                f'after acltool({action}, traverse=True)'
            )

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_child_dirs_have_default_entries(self, posix_traverse_env, action):
        """Directories in child dataset must retain default ACL entries."""
        root, subdir, file_root, file_sub, \
            child_mnt, child_subdir, child_file_root, child_file_sub = posix_traverse_env

        _run_acltool(root, action, traverse=True)

        for path in (child_mnt, child_subdir):
            acl = _get_acl(path, is_dir=True)
            assert isinstance(acl, t.POSIXACL)
            assert acl.default_aces, (
                f'{path}: child dir must have default ACL entries '
                f'after acltool({action}, traverse=True)'
            )

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_child_matches_parent_for_files(self, posix_traverse_env, action):
        """Files in child dataset must have same ACL structure as parent files."""
        root, subdir, file_root, file_sub, \
            child_mnt, child_subdir, child_file_root, child_file_sub = posix_traverse_env

        _run_acltool(root, action, traverse=True)

        parent_acl = _get_acl(file_root)
        child_acl = _get_acl(child_file_root)

        assert isinstance(child_acl, t.POSIXACL)
        assert not child_acl.default_aces
        assert len(child_acl.aces) == len(parent_acl.aces), (
            'child file ACL must have same number of access entries as parent file'
        )

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_child_matches_parent_for_dirs(self, posix_traverse_env, action):
        """Dirs in child dataset must have same ACL structure as parent dirs."""
        root, subdir, file_root, file_sub, \
            child_mnt, child_subdir, child_file_root, child_file_sub = posix_traverse_env

        _run_acltool(root, action, traverse=True)

        parent_acl = _get_acl(subdir, is_dir=True)
        child_acl = _get_acl(child_subdir, is_dir=True)

        assert isinstance(child_acl, t.POSIXACL)
        assert child_acl.default_aces
        assert len(child_acl.aces) == len(parent_acl.aces), (
            'child dir ACL must have same number of access entries as parent dir'
        )
        assert len(child_acl.default_aces) == len(parent_acl.default_aces), (
            'child dir ACL must have same number of default entries as parent dir'
        )


# ---------------------------------------------------------------------------
# NFS4 tests (no traverse)
# ---------------------------------------------------------------------------

class TestAcltoolNFS4:

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_files_get_nfs4_acl(self, nfs4_env, action):
        """Files must receive an NFS4 ACL with access entries after acltool()."""
        root, subdir, file_root, file_sub = nfs4_env
        _run_acltool(root, action)

        for path in (file_root, file_sub):
            acl = _get_acl(path)
            assert isinstance(acl, t.NFS4ACL), (
                f'{path}: expected NFS4ACL after acltool({action})'
            )
            assert acl.aces, (
                f'{path}: file NFS4ACL must have at least one ACE '
                f'after acltool({action})'
            )

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_dirs_get_nfs4_acl(self, nfs4_env, action):
        """Directories must receive an NFS4 ACL with access entries after acltool()."""
        root, subdir, file_root, file_sub = nfs4_env
        _run_acltool(root, action)

        for path in (root, subdir):
            acl = _get_acl(path, is_dir=True)
            assert isinstance(acl, t.NFS4ACL), (
                f'{path}: expected NFS4ACL after acltool({action})'
            )
            assert acl.aces, (
                f'{path}: dir NFS4ACL must have at least one ACE '
                f'after acltool({action})'
            )

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_file_aces_have_no_inherit_flags(self, nfs4_env, action):
        """File ACEs must not carry FILE_INHERIT or DIRECTORY_INHERIT flags."""
        root, subdir, file_root, file_sub = nfs4_env
        _run_acltool(root, action)

        inherit_flags = t.NFS4Flag.FILE_INHERIT | t.NFS4Flag.DIRECTORY_INHERIT
        for path in (file_root, file_sub):
            acl = _get_acl(path)
            for ace in acl.aces:
                assert not (ace.ace_flags & inherit_flags), (
                    f'{path}: file ACE must not carry FILE_INHERIT or '
                    f'DIRECTORY_INHERIT after acltool({action})'
                )


# ---------------------------------------------------------------------------
# NFS4 tests (traverse=True)
# ---------------------------------------------------------------------------

class TestAcltoolNFS4Traverse:

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_child_files_get_nfs4_acl(self, nfs4_traverse_env, action):
        """Files in child dataset must receive an NFS4 ACL after acltool(traverse=True)."""
        root, subdir, file_root, file_sub, \
            child_mnt, child_subdir, child_file_root, child_file_sub = nfs4_traverse_env

        _run_acltool(root, action, traverse=True)

        for path in (child_file_root, child_file_sub):
            acl = _get_acl(path)
            assert isinstance(acl, t.NFS4ACL), (
                f'{path}: expected NFS4ACL after acltool({action}, traverse=True)'
            )
            assert acl.aces, (
                f'{path}: child file NFS4ACL must have at least one ACE'
            )

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_child_dirs_get_nfs4_acl(self, nfs4_traverse_env, action):
        """Dirs in child dataset must receive an NFS4 ACL after acltool(traverse=True)."""
        root, subdir, file_root, file_sub, \
            child_mnt, child_subdir, child_file_root, child_file_sub = nfs4_traverse_env

        _run_acltool(root, action, traverse=True)

        for path in (child_mnt, child_subdir):
            acl = _get_acl(path, is_dir=True)
            assert isinstance(acl, t.NFS4ACL), (
                f'{path}: expected NFS4ACL after acltool({action}, traverse=True)'
            )
            assert acl.aces, (
                f'{path}: child dir NFS4ACL must have at least one ACE'
            )

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_child_matches_parent_for_files(self, nfs4_traverse_env, action):
        """Files in child dataset must have same ACE count as parent files."""
        root, subdir, file_root, file_sub, \
            child_mnt, child_subdir, child_file_root, child_file_sub = nfs4_traverse_env

        _run_acltool(root, action, traverse=True)

        parent_acl = _get_acl(file_root)
        child_acl = _get_acl(child_file_root)

        assert isinstance(child_acl, t.NFS4ACL)
        assert len(child_acl.aces) == len(parent_acl.aces), (
            'child file ACL must have same number of ACEs as parent file'
        )

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_child_matches_parent_for_dirs(self, nfs4_traverse_env, action):
        """Dirs in child dataset must have same ACE count as parent dirs."""
        root, subdir, file_root, file_sub, \
            child_mnt, child_subdir, child_file_root, child_file_sub = nfs4_traverse_env

        _run_acltool(root, action, traverse=True)

        parent_acl = _get_acl(subdir, is_dir=True)
        child_acl = _get_acl(child_subdir, is_dir=True)

        assert isinstance(child_acl, t.NFS4ACL)
        assert len(child_acl.aces) == len(parent_acl.aces), (
            'child dir ACL must have same number of ACEs as parent dir'
        )


# ---------------------------------------------------------------------------
# do_chmod / stripacl regression tests
#
# Bugs fixed:
#
# 1. setperm(recursive=True, stripacl=True, mode=...) was passing
#    AclToolAction.CLONE to acltool().  acltool then called
#    NFS4ACL.generate_inherited_acl() on the just-stripped (trivial, no
#    inherit-flags) ACL, raising:
#      ValueError: parent ACL has no inheritable ACEs for this object type
#
# 2. acltool() set do_chmod=True unconditionally, so a CLONE pass (setting
#    a proper inherited NFS4 ACL on children) also chmoded every child to
#    the root mode — wrong on NFS4 where mode bits are derived from the ACL.
# ---------------------------------------------------------------------------

def _strip_acl(path):
    """Strip the ACL from path via fsetacl(fd, None)."""
    fd = t.openat2(path, flags=os.O_RDONLY, resolve=t.RESOLVE_NO_SYMLINKS)
    try:
        t.fsetacl(fd, None)
    finally:
        os.close(fd)


def _get_mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class TestAcltoolChmod:

    def test_strip_with_mode_applies_mode_to_children(self, nfs4_env):
        """
        STRIP action with do_chmod=True must apply root_mode to every child.

        Regression: setperm(recursive=True, stripacl=True, mode=...) was
        broken on NFS4 because it chose CLONE instead of STRIP, then crashed
        when generate_inherited_acl() found no inherit flags on the stripped
        root ACL.
        """
        root, subdir, file_root, file_sub = nfs4_env

        # Strip the root ACL so acltool sees a trivial ACL (no inherit flags).
        # This is exactly what filesystem.setperm does before calling acltool.
        _strip_acl(root)

        target_mode = 0o700
        fd = t.openat2(root, flags=os.O_RDONLY, resolve=t.RESOLVE_NO_SYMLINKS)
        try:
            os.fchmod(fd, target_mode)
            # Must not raise ValueError despite trivial (no-inherit) root ACL.
            AclTool(fd, AclToolAction.STRIP, ACL_UNDEFINED_ID, ACL_UNDEFINED_ID,
                    ATPermOptions(target_mode=target_mode)).run()
        finally:
            os.close(fd)

        for path in (subdir, file_root, file_sub):
            assert _get_mode(path) == target_mode, (
                f'{path}: expected mode {target_mode:o} after STRIP+do_chmod'
            )

    def test_strip_without_mode_does_not_chmod_children(self, nfs4_env):
        """STRIP action with do_chmod=False must leave child modes unchanged."""
        root, subdir, file_root, file_sub = nfs4_env

        mode_before = {p: _get_mode(p) for p in (subdir, file_root, file_sub)}

        _strip_acl(root)
        fd = t.openat2(root, flags=os.O_RDONLY, resolve=t.RESOLVE_NO_SYMLINKS)
        try:
            AclTool(fd, AclToolAction.STRIP, ACL_UNDEFINED_ID, ACL_UNDEFINED_ID,
                    ATPermOptions()).run()
        finally:
            os.close(fd)

        for path in (subdir, file_root, file_sub):
            assert _get_mode(path) == mode_before[path], (
                f'{path}: mode must be unchanged with do_chmod=False'
            )

    def test_clone_nfs4_without_mode_does_not_chmod_children(self, nfs4_env):
        """
        CLONE action with do_chmod=False must not fchmod children to the
        root's stored mode.

        On NFS4 (aclmode=passthrough) setting an inherited ACL on a child
        automatically updates its mode bits to match the ACL (FULL_CONTROL →
        0o777).  Root's *stored* mode is set to 0o700 so it diverges from the
        ACL-derived value.  With do_chmod=False children must end up at the
        ACL-derived 0o777; do_chmod=True would fchmod them back to 0o700.
        """
        root, subdir, file_root, file_sub = nfs4_env

        fd = t.openat2(root, flags=os.O_RDONLY, resolve=t.RESOLVE_NO_SYMLINKS)
        try:
            root_acl = t.fgetacl(fd)
            # Diverge root's stored mode from what the ACL implies.
            os.fchmod(fd, 0o700)
            AclTool(fd, AclToolAction.CLONE, ACL_UNDEFINED_ID, ACL_UNDEFINED_ID,
                    ATAclOptions(target_acl=root_acl)).run()
        finally:
            os.close(fd)

        # ZFS derives mode bits from the inherited FULL_CONTROL ACL → 0o777.
        # do_chmod=False must not override that with the root's stored 0o700.
        for path in (subdir, file_root, file_sub):
            assert _get_mode(path) == 0o777, (
                f'{path}: expected ACL-derived mode 777, got {_get_mode(path):o}'
            )


# ---------------------------------------------------------------------------
# aclmode=restricted + non-trivial ACL regression tests
#
# On aclmode=restricted fchmod() raises EPERM when a non-trivial ACL is
# present.  All children in nfs4_restricted_env carry a non-trivial ACL, so
# any accidental chmod during a CLONE pass will surface as an immediate EPERM
# rather than a silent wrong-mode value.  This makes the restricted fixture a
# stronger regression guard than the passthrough tests above.
# ---------------------------------------------------------------------------

class TestAcltoolNFS4Restricted:

    def test_fchmod_raises_eperm_on_restricted_nontrivial(self, nfs4_restricted_env):
        """
        Sanity check: fchmod on a file with a non-trivial ACL on an
        aclmode=restricted dataset must raise EPERM.

        This confirms the fixture actually enforces the restriction so the
        CLONE tests below are meaningful.
        """
        _, _, file_root, _ = nfs4_restricted_env
        fd = t.openat2(file_root, flags=os.O_RDONLY, resolve=t.RESOLVE_NO_SYMLINKS)
        try:
            with pytest.raises(OSError) as exc_info:
                os.fchmod(fd, 0o644)
            assert exc_info.value.errno == errno.EPERM, (
                'expected EPERM from fchmod on restricted dataset with non-trivial ACL'
            )
        finally:
            os.close(fd)

    @pytest.mark.parametrize('action', _CLONE_INHERIT)
    def test_clone_restricted_without_mode_does_not_chmod(self, nfs4_restricted_env, action):
        """
        CLONE/INHERIT with do_chmod=False must not attempt fchmod on children.

        If acltool() erroneously called fchmod() on children that already
        carry a non-trivial ACL on an aclmode=restricted dataset, it would
        raise EPERM and the test would fail.
        """
        root, subdir, file_root, file_sub = nfs4_restricted_env

        fd = t.openat2(root, flags=os.O_RDONLY, resolve=t.RESOLVE_NO_SYMLINKS)
        try:
            root_acl = t.fgetacl(fd)
            # Must not raise EPERM (or anything else).
            AclTool(fd, action, ACL_UNDEFINED_ID, ACL_UNDEFINED_ID,
                    ATAclOptions(target_acl=root_acl)).run()
        finally:
            os.close(fd)

        # All children must still carry a non-trivial NFS4 ACL.
        for path, is_dir in ((subdir, True), (file_root, False), (file_sub, False)):
            acl = _get_acl(path, is_dir=is_dir)
            assert isinstance(acl, t.NFS4ACL)
            assert not acl.trivial, (
                f'{path}: ACL must remain non-trivial after {action} with do_chmod=False'
            )
