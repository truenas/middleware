import errno
import stat
import os
from copy import deepcopy

import pytest

from auto_config import pool_name
from middlewared.service_exception import CallError
from middlewared.test.integration.assets.filesystem import directory
from middlewared.test.integration.assets.pool import dataset as create_dataset
from middlewared.test.integration.utils import call, ssh


@pytest.mark.parametrize('path', ('/boot/grub', '/root', '/bin', '/usr/bin'))
def test_filesystem_stat_results_for_path_(spath):
    results = call('filesystem.stat', spath)
    for key in (
        'allocation_size', 'size', 'mode',
        'dev', 'inode', 'uid', 'gid', 'nlink',
        'mount_id', 'dev', 'inode'
    ):
        assert isinstance(results[key], int)
        if key in ('uid', 'gid'):
            assert results[key] == 0
        elif key == 'nlink':
            assert -1 < results[key] < 10

    for key in ('atime', 'mtime', 'ctime'):
        assert isinstance(results[key], float)

    for key in ('user', 'group'):
        assert results[key] == 'root'

    assert results['acl'] is False
    if spath == '/bin':
        assert results['type'] == 'SYMLINK'
        assert results['realpath'] == '/usr/bin'
    else:
        assert results['type'] == 'DIRECTORY'
        assert results['realpath'] == spath


def test_filesystem_statfs_fstype():
    parent_path = f'/mnt/{pool_name}'
    data = call('filesystem.statfs', parent_path)
    assert data['fstype'] == 'zfs', data['fstype']
    nested_path = f'{parent_path}/tmpfs'
    ssh(f'mkdir -p {nested_path}; mount -t tmpfs -o size=10M tmpfstest {nested_path}')
    data = call('filesystem.statfs', nested_path)
    assert data['fstype'] == 'tmpfs', data['fstype']
    ssh(f'umount {nested_path}; rmdir {nested_path}')


def test_immutable_flag():
    t_path = os.path.join('/mnt', pool_name, 'random_directory_immutable')
    t_child_path = os.path.join(t_path, 'child')
    with directory(t_path) as d:
        for flag_set in (True, False):
            call('filesystem.set_immutable',  flag_set, d)
            # We test 2 things
            # 1) Writing content to the parent path fails/succeeds based on "set"
            # 2) "is_immutable_set" returns sane response
            if flag_set:
                with pytest.raises(PermissionError):
                    call('filesystem.mkdir', f'{t_child_path}_{flag_set}')
            else:
                call('filesystem.mkdir', f'{t_child_path}_{flag_set}')

            is_immutable = call('filesystem.is_immutable', t_path)
            err = 'Immutable flag is still not set'
            if not flag_set:
                err = 'Immutable flag is still set'
            assert is_immutable == flag_set, err


def test_filesystem_listdir_exclude_non_mounts():
    with directory('/mnt/random_dir'):
        # exclude dirs at root of /mnt since this
        # directory is used exclusively to mount zpools
        for i in call('filesystem.listdir', '/mnt'):
            assert i['name'] != 'random_dir'


def test_filesystem_stat_filetype():
    """
    This test checks that file types are properly
    identified through the filesystem plugin in middleware.
    There is an additional check to make sure that paths
    in the ZFS CTL directory (.zfs) are properly flagged.
    """
    ds_name = 'stat_test'
    targets = ('file', 'directory', 'symlink', 'other')
    with create_dataset(ds_name) as ds:
        base = f'/mnt/{ds}'
        ssh(' && '.join((
            f'mkdir {base}/directory',
            f'touch {base}/file',
            f'ln -s {base}/file {base}/symlink',
            f'mkfifo {base}/other'
        )))
        for x in targets:
            statout = call('filesystem.stat', f'{base}/{x}')
            assert statout['type'] == x.upper()
            assert not statout['is_ctldir']

        snap_name = f'{ds_name}_snap1'
        call('zfs.snapshot.create', {
            'dataset': ds,
            'name': snap_name,
            'recursive': False,
        })
        for x in targets:
            target = f'{base}/.zfs/snapshot/{snap_name}/{x}'
            statout = call('filesystem.stat', target)
            assert statout['type'] == x.upper()
            assert statout['is_ctldir']

        assert call('filesystem.stat', f'{base}/.zfs/snapshot/{snap_name}')['is_ctldir']
        assert all(dirent['is_ctldir'] for dirent in call(
            'filesystem.listdir', f'{base}/.zfs/snapshot', [], {'select': ['name', 'is_ctldir']}
        ))
        assert call('filesystem.stat', f'{base}/.zfs/snapshot')['is_ctldir']
        assert all(dirent['is_ctldir'] for dirent in call(
            'filesystem.listdir', f'{base}/.zfs', [], {'select': ['name', 'is_ctldir']}
        ))
        assert call('filesystem.stat', f'{base}/.zfs')['is_ctldir']


def test_fiilesystem_statfs_flags():
    """
    This test verifies that changing ZFS properties via
    middleware causes mountinfo changes visible via statfs.
    """
    properties = (
        # tuple: ZFS property name, property value, mountinfo value
        ("readonly", "ON", "RO"),
        ("readonly", "OFF", "RW"),
        ("atime", "OFF", "NOATIME"),
        ("exec", "OFF", "NOEXEC"),
        ("acltype", "NFSV4", "NFS4ACL"),
        ("acltype", "POSIX", "POSIXACL"),
    )
    with create_dataset('statfs_test') as ds:
        base = f'/mnt/{ds}'
        payload = {'name': ds}
        for p in properties:
            # set option we're checking and make sure it's really set
            payload.update({p[0]: p[1]})
            if p[0] == 'acltype':
                payload.update({'aclmode': 'RESTRICTED' if p[1] == 'NFSV4' else 'DISCARD'})
            assert call('pool.dataset.update', payload)['value'] == p[1]

            # check statfs results
            mount_flags = call('filesystem.statfs', base)['flags']
            assert p[2] in mount_flags, f'{base}: ({p[2]}) not in {mount_flags}'


def test_dosmodes():
    modes = ('readonly', 'hidden', 'system', 'archive', 'offline', 'sparse')
    with create_dataset('dosmode_test') as ds:
        base = f'/mnt/{ds}'
        testpaths = (f'{base}/testfile', f'{base}/testdir')
        ssh(f'touch {testpaths[0]}; mkdir {testpaths[1]}')
        for p in testpaths:
            expected_flags = call('filesystem.get_zfs_attributes', p)
            for m in modes:
                to_set = {m: not expected_flags[m]}
                res = call('filesystem.set_zfs_attributes', {'path': p, 'zfs_file_attributes': to_set})
                expected_flags.update(to_set)
                assert expected_flags == res
                res = call('filesystem.get_zfs_attributes', p)
                assert expected_flags == res


def test_acl_path_execute_validation():
    perm = {'BASIC': 'FULL_CONTROL'}
    flag = {'BASIC': 'INHERIT'}
    NFSV4_DACL = [
        {'tag': 'owner@', 'id': -1, 'type': 'ALLOW', 'perms': perm, 'flags': flag},
        {'tag': 'group@', 'id': -1, 'type': 'ALLOW', 'perms': perm, 'flags': flag},
        {'tag': 'USER', 'id': 65534, 'type': 'ALLOW', 'perms': perm, 'flags': flag},
        {'tag': 'GROUP', 'id': 65534, 'type': 'ALLOW', 'perms': perm, 'flags': flag},
    ]
    with create_dataset(
        'acl_ex_test',
        {'acltype': 'NFSV4', 'aclmode': 'PASSTHROUGH'},
        {'mode': 770}
    ) as ds:
        path = f'/mnt/{ds}'
        """
        For NFSv4 ACLs four different tags generate user tokens differently:
        1) owner@ tag will test `uid` from payload
        2) group@ tag will test `gid` from payload
        3) GROUP will test the `id` in payload with id_type
        4) USER will test the `id` in mayload with USER id_type
        """
        # Start with testing denials
        with create_dataset(f'{ds}/sub', {'acltype': 'NFSV4', 'aclmode': 'PASSTHROUGH'}) as sub_ds:
            sub_path = f'/mnt/{sub_ds}'
            acl = deepcopy(NFSV4_DACL)
            names = ('daemon', 'apps', 'nobody', 'nogroup')
            for idx, entry in enumerate(NFSV4_DACL):
                rv = call('filesystem.setacl', {'path': sub_path, "dacl": acl, 'uid': 1, 'gid': 568})
                # all of these tests should fail
                assert rv['state'] == 'FAILED', rv
                assert names[idx] in rv['results']['error'], rv['results']['error']
                acl.pop(0)

            # when this test starts, we have 770 perms on parent
            for entry in NFSV4_DACL:
                # first set permissions on parent dataset
                if entry['tag'] == 'owner@':
                    job_status = call('filesystem.chown', {
                        'path': path,
                        'uid': 1,
                        'gid': 0
                    })
                elif entry['tag'] == 'group@':
                    job_status = call('filesystem.chown', {
                        'path': path,
                        'uid': 0,
                        'gid': 568
                    })
                elif entry['tag'] == 'USER':
                    job_status = call('filesystem.setacl', {
                        'path': path,
                        'uid': 0,
                        'gid': 0,
                        'dacl': [entry]
                    })
                elif entry['tag'] == 'GROUP':
                    job_status = call('filesystem.setacl', {
                        'path': path,
                        'uid': 0,
                        'gid': 0,
                        'dacl': [entry]
                    })
                assert job_status['state'] == 'SUCCESS', job_status

                # Now set the acl on child dataset. This should succeed
                job_status = call('filesystem.setacl', {
                    'path': sub_path,
                    'uid': 1,
                    'gid': 568,
                    'dacl': [entry]
                })
                assert job_status['state'] == 'SUCCESS', job_status


@pytest.fixture(scope="module")
def file_and_directory():
    with create_dataset("test_file_and_directory") as ds:
        ssh(f"mkdir /mnt/{ds}/test-directory; touch /mnt/{ds}/test-file")
        yield ds


@pytest.mark.parametrize("query,result", [
    ([], {"test-directory", "test-file"}),
    ([["type", "=", "DIRECTORY"]], {"test-directory"}),
    ([["type", "!=", "DIRECTORY"]], {"test-file"}),
    ([["type", "=", "FILE"]], {"test-file"}),
    ([["type", "!=", "FILE"]], {"test-directory"}),
])
def test_type_filter(file_and_directory, query, result):
    listdir = call("filesystem.listdir", f"/mnt/{file_and_directory}", query)
    assert {item["name"] for item in listdir} == result, listdir


def test_mkdir_mode():
    with create_dataset("test_mkdir_mode") as ds:
        testdir = os.path.join("/mnt", ds, "testdir")
        call("filesystem.mkdir", {'path': testdir, 'options': {'mode': '777'}})
        st = call("filesystem.stat", testdir)
        assert stat.S_IMODE(st["mode"]) == 0o777


def test_mkdir_chmod_failure():
    with create_dataset("test_mkdir_chmod", {"share_type": "SMB"}) as ds:
        testdir = os.path.join("/mnt", ds, "testdir")
        with pytest.raises(PermissionError):
            call("filesystem.mkdir", {'path': testdir, 'options': {'mode': '777'}})
        with pytest.raises(CallError) as ce:
            call("filesystem.stat", testdir)
        assert ce.value.errno == errno.ENOENT
        mkdir_st = call("filesystem.mkdir", {'path': testdir, 'options': {'mode': '777', 'raise_chmod_error': False}})
        st = call("filesystem.stat", testdir)
        # Verify that mode output returned from mkdir matches what was actually set
        assert st['mode'] == mkdir_st['mode']
        # mkdir succeeded, but chmod failed so we get mode based on inherited ACL (SMB preset)
        assert stat.S_IMODE(st["mode"]) == 0o770
