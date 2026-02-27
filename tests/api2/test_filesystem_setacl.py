"""
Tests for filesystem.setacl covering recursive, traverse, and strip behaviour.

Functional validation of the truenas_os-based ACL engine is in
tests/unit/test_filesystem_acl.py; these tests focus on the middleware API
surface (job execution, option propagation, dataset boundary handling).
"""


from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

NFS4_DACL = [
    {'tag': 'owner@',    'id': -1, 'type': 'ALLOW',
     'perms': {'BASIC': 'FULL_CONTROL'}, 'flags': {'BASIC': 'INHERIT'}},
    {'tag': 'group@',    'id': -1, 'type': 'ALLOW',
     'perms': {'BASIC': 'FULL_CONTROL'}, 'flags': {'BASIC': 'INHERIT'}},
    {'tag': 'everyone@', 'id': -1, 'type': 'ALLOW',
     'perms': {'BASIC': 'TRAVERSE'},    'flags': {'BASIC': 'INHERIT'}},
]

POSIX_DACL = [
    {'tag': 'USER_OBJ',  'id': -1, 'default': False,
     'perms': {'READ': True,  'WRITE': True,  'EXECUTE': True}},
    {'tag': 'GROUP_OBJ', 'id': -1, 'default': False,
     'perms': {'READ': True,  'WRITE': False, 'EXECUTE': True}},
    {'tag': 'OTHER',     'id': -1, 'default': False,
     'perms': {'READ': False, 'WRITE': False, 'EXECUTE': False}},
    # default entries required for recursive application
    {'tag': 'USER_OBJ',  'id': -1, 'default': True,
     'perms': {'READ': True,  'WRITE': True,  'EXECUTE': True}},
    {'tag': 'GROUP_OBJ', 'id': -1, 'default': True,
     'perms': {'READ': True,  'WRITE': False, 'EXECUTE': True}},
    {'tag': 'OTHER',     'id': -1, 'default': True,
     'perms': {'READ': False, 'WRITE': False, 'EXECUTE': False}},
]


def _has_acl(path: str) -> bool:
    return call('filesystem.stat', path)['acl']


def _populate(base: str) -> None:
    """Create a shallow directory tree for recursive/traverse tests."""
    ssh(f'mkdir -p {base}/dir1/dir2 && touch {base}/dir1/file1 {base}/dir1/dir2/file2')


# ---------------------------------------------------------------------------
# Recursive
# ---------------------------------------------------------------------------

def test_setacl_nfs4_recursive():
    """setacl with recursive=True propagates NFS4 ACL to all descendants."""
    with dataset('setacl_rec_nfs4', {'share_type': 'SMB'}) as ds:
        base = f'/mnt/{ds}'
        _populate(base)

        call('filesystem.setacl', {
            'path': base,
            'dacl': NFS4_DACL,
            'options': {'recursive': True},
        }, job=True)

        for path in (
            f'{base}/dir1',
            f'{base}/dir1/file1',
            f'{base}/dir1/dir2',
            f'{base}/dir1/dir2/file2',
        ):
            assert _has_acl(path), f'{path}: expected ACL after recursive setacl'


def test_setacl_posix_recursive():
    """setacl with recursive=True propagates POSIX ACL to all descendants."""
    with dataset('setacl_rec_posix',
                 {'acltype': 'POSIX', 'aclmode': 'DISCARD'}) as ds:
        base = f'/mnt/{ds}'
        _populate(base)

        call('filesystem.setacl', {
            'path': base,
            'dacl': POSIX_DACL,
            'options': {'recursive': True},
        }, job=True)

        for path in (
            f'{base}/dir1',
            f'{base}/dir1/file1',
            f'{base}/dir1/dir2',
            f'{base}/dir1/dir2/file2',
        ):
            assert _has_acl(path), f'{path}: expected POSIX ACL after recursive setacl'


# ---------------------------------------------------------------------------
# Traverse
# ---------------------------------------------------------------------------

def test_setacl_no_traverse_stops_at_child_dataset():
    """Without traverse, setacl does not cross into child dataset boundaries."""
    with dataset('setacl_notraverse', {'share_type': 'SMB'}) as parent_ds:
        with dataset('setacl_notraverse/child', {'share_type': 'SMB'}) as child_ds:
            child = f'/mnt/{child_ds}'
            ssh(f'touch {child}/canary')

            acl_before = call('filesystem.getacl', child)['acl']

            call('filesystem.setacl', {
                'path': f'/mnt/{parent_ds}',
                'dacl': NFS4_DACL,
                'options': {'recursive': True},
            }, job=True)

            assert call('filesystem.getacl', child)['acl'] == acl_before, (
                'child dataset ACL should be unchanged without traverse'
            )


def test_setacl_traverse_crosses_child_dataset():
    """With traverse=True, setacl propagates ACL across child dataset boundaries."""
    with dataset('setacl_traverse', {'share_type': 'SMB'}) as parent_ds:
        with dataset('setacl_traverse/child', {'share_type': 'SMB'}) as child_ds:
            child = f'/mnt/{child_ds}'
            ssh(f'touch {child}/canary')

            call('filesystem.setacl', {
                'path': f'/mnt/{parent_ds}',
                'dacl': NFS4_DACL,
                'options': {'recursive': True, 'traverse': True},
            }, job=True)

            assert _has_acl(f'{child}/canary'), (
                'file inside child dataset should have ACL after traverse setacl'
            )


# ---------------------------------------------------------------------------
# Strip
# ---------------------------------------------------------------------------

def test_setacl_strip_nonrecursive():
    """stripacl=True without recursive removes ACL from root only."""
    with dataset('setacl_strip_single', {'share_type': 'SMB'}) as ds:
        base = f'/mnt/{ds}'
        ssh(f'mkdir {base}/subdir')

        assert _has_acl(base)
        assert _has_acl(f'{base}/subdir')

        call('filesystem.setacl', {
            'path': base,
            'dacl': [],
            'options': {'stripacl': True},
        }, job=True)

        assert not _has_acl(base), 'root ACL should be stripped'
        assert _has_acl(f'{base}/subdir'), 'child ACL should be untouched'


def test_setacl_strip_recursive():
    """stripacl=True with recursive=True removes ACL from root and all descendants."""
    with dataset('setacl_strip_rec', {'share_type': 'SMB'}) as ds:
        base = f'/mnt/{ds}'
        _populate(base)

        call('filesystem.setacl', {
            'path': base,
            'dacl': [],
            'options': {'stripacl': True, 'recursive': True},
        }, job=True)

        for path in (
            base,
            f'{base}/dir1',
            f'{base}/dir1/file1',
            f'{base}/dir1/dir2',
            f'{base}/dir1/dir2/file2',
        ):
            assert not _has_acl(path), f'{path}: ACL should have been stripped'
