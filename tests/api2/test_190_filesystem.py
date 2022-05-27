#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)

from functions import POST, SSH_TEST
from auto_config import dev_test, pool_name, ip, user, password
from middlewared.test.integration.assets.filesystem import directory
from utils import create_dataset

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')
group = 'root'
path = '/etc'
path_list = ['default', 'kernel', 'zfs', 'ssh']
random_path = ['/boot/grub', '/root', '/bin', '/usr/bin']


def test_01_get_filesystem_listdir():
    results = POST('/filesystem/listdir/', {'path': path})
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    assert len(results.json()) > 0, results.text
    global listdir
    listdir = results


@pytest.mark.parametrize('name', path_list)
def test_02_looking_at_listdir_path_(name):
    for dline in listdir.json():
        if dline['path'] == f'{path}/{name}':
            assert dline['type'] in ('DIRECTORY', 'FILE'), listdir.text
            assert dline['uid'] == 0, listdir.text
            assert dline['gid'] == 0, listdir.text
            assert dline['name'] == name, listdir.text
            break
    else:
        raise AssertionError(f'/{path}/{name} not found')


@pytest.mark.parametrize('path', random_path)
def test_03_get_filesystem_stat_(path):
    results = POST('/filesystem/stat/', path)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    assert isinstance(results.json()['size'], int) is True, results.text
    assert isinstance(results.json()['mode'], int) is True, results.text
    assert results.json()['uid'] == 0, results.text
    assert results.json()['gid'] == 0, results.text
    assert isinstance(results.json()['atime'], float) is True, results.text
    assert isinstance(results.json()['mtime'], float) is True, results.text
    assert isinstance(results.json()['ctime'], float) is True, results.text
    assert isinstance(results.json()['dev'], int) is True, results.text
    assert isinstance(results.json()['inode'], int) is True, results.text
    assert results.json()['nlink'] in tuple(range(10)), results.text
    assert results.json()['user'] == 'root', results.text
    assert results.json()['group'] == group, results.text
    assert results.json()['acl'] is False, results.text


def test_04_test_filesystem_statfs_fstype():
    # test zfs fstype first
    parent_path = f'/mnt/{pool_name}'
    results = POST('/filesystem/statfs/', parent_path)
    assert results.status_code == 200, results.text
    data = results.json()
    assert data, results.text
    assert data['fstype'] == 'zfs', data['fstype']

    # mount nested tmpfs entry and make sure statfs
    # returns `tmpfs` as the fstype
    # mkdir
    nested_path = f'{parent_path}/tmpfs'
    cmd1 = f'mkdir -p {nested_path}'
    results = SSH_TEST(cmd1, user, password, ip)
    assert results['result'] is True, results['output']

    # mount tmpfs
    cmd2 = f'mount -t tmpfs -o size=10M tmpfstest {nested_path}'
    results = SSH_TEST(cmd2, user, password, ip)
    assert results['result'] is True, results['output']

    # test fstype
    results = POST('/filesystem/statfs/', nested_path)
    assert results.status_code == 200, results.text
    data = results.json()
    assert data, results.text
    assert data['fstype'] == 'tmpfs', data['fstype']

    # cleanup
    cmd3 = f'umount {nested_path}'
    results = SSH_TEST(cmd3, user, password, ip)
    assert results['result'] is True, results['output']
    cmd4 = f'rmdir {nested_path}'
    results = SSH_TEST(cmd4, user, password, ip)
    assert results['result'] is True, results['output']


def test_05_set_immutable_flag_on_path():
    t_path = os.path.join('/mnt', pool_name, 'random_directory_immutable')
    t_child_path = os.path.join(t_path, 'child')

    with directory(t_path) as d:
        for flag_set in (True, False):
            POST('/filesystem/set_immutable/', {'set_flag': flag_set, 'path': d})
            # We test 2 things
            # 1) Writing content to the parent path fails/succeeds based on "set"
            # 2) "is_immutable_set" returns sane response
            results = POST('/filesystem/mkdir', f'{t_child_path}_{flag_set}')
            assert results.status_code == (500 if flag_set else 200), results.text

            results = POST('/filesystem/is_immutable/', t_path)
            assert results.status_code == 200, results.text
            result = results.json()
            assert isinstance(result, bool) is True, results.text
            assert result == flag_set, 'Immutable flag is still not set' if flag_set else 'Immutable flag is still set'


def test_06_test_filesystem_listdir_exclude_non_mounts():
    # create a random directory at top-level of '/mnt'
    mnt = '/mnt/'
    randir = 'random_dir'
    path = mnt + randir

    with directory(path) as _:
        # now call filesystem.listdir specifying '/mnt' as path
        # and ensure `randir` is not in the output
        results = POST('/filesystem/listdir/', {'path': mnt})
        assert results.status_code == 200, results.text
        assert not any(i['name'] == randir for i in results.json()), f'{randir} should not be listed'


def test_07_test_filesystem_stat_filetype():
     """
     This test checks that file types are properly
     identified through the filesystem plugin in middleware.
     There is an additional check to make sure that paths
     in the ZFS CTL directory (.zfs) are properly flagged.
     """
     ds_name = 'stat_test'
     snap_name = f'{ds_name}_snap1'
     path = f'/mnt/{pool_name}/{ds_name}'
     targets = ['file', 'directory', 'symlink', 'other']
     cmds = [
         f'mkdir {path}/directory',
         f'touch {path}/file',
         f'ln -s {path}/file {path}/symlink',
         f'mkfifo {path}/other'
     ]

     with create_dataset(f'{pool_name}/{ds_name}'):
         results = SSH_TEST(' && '.join(cmds), user, password, ip)
         assert results['result'] is True, str(results)

         for x in targets:
             target = f'{path}/{x}'
             results = POST('/filesystem/stat/', target)
             assert results.status_code == 200, f'{target}: {results.text}'
             statout = results.json()

             assert statout['type'] == x.upper(), str(statout)
             assert not statout['is_ctldir']

         result = POST("/zfs/snapshot/", {
             'dataset': f'{pool_name}/{ds_name}',
             'name': snap_name,
             'recursive': False,
         })
         assert result.status_code == 200, result.text

         for x in targets:
             target = f'{path}/.zfs/snapshot/{snap_name}/{x}'
             results = POST('/filesystem/stat/', target)
             assert results.status_code == 200, f'{target}: {results.text}'
             statout = results.json()

             assert statout['type'] == x.upper(), str(statout)
             assert statout['is_ctldir']

         results = POST('/filesystem/stat/', f'{path}/.zfs/snapshot/{snap_name}')
         assert results.status_code == 200, results.text
         assert results.json()['is_ctldir']

         results = POST('/filesystem/stat/', f'{path}/.zfs/snapshot')
         assert results.status_code == 200, results.text
         assert results.json()['is_ctldir']

         results = POST('/filesystem/stat/', f'{path}/.zfs')
         assert results.status_code == 200, results.text
         assert results.json()['is_ctldir']


def test_08_test_fiilesystem_statfs_flags():
     """
     This test verifies that changing ZFS properties via
     middleware causes mountinfo changes visible via statfs.
     """
     ds_name = 'statfs_test'
     target = f'{pool_name}/{ds_name}'
     target_url = target.replace('/', '%2F')
     path = f'/mnt/{target}'

     # tuple: ZFS property name, property value, mountinfo value
     properties = [
         ("readonly", "ON", "RO"),
         ("readonly", "OFF", "RW"),
         ("atime", "OFF", "NOATIME"),
         ("exec", "OFF", "NOEXEC"),
         ("acltype", "NFSV4", "NFS4ACL"),
         ("acltype", "POSIX", "POSIXACL"),
     ]

     with create_dataset(target):
         for p in properties:
             # set option we're checking and make sure it's really set
             payload = {
                 p[0]: p[1]
             }
             if p[0] == 'acltype':
                 payload.update({
                     'aclmode': 'RESTRICTED' if p[1] == 'NFSV4' else 'DISCARD'
                 })
             results = PUT(f'/pool/dataset/id/{target_url}', payload)
             assert results.status_code == 200, results.text
             prop_out = results.json()[p[0]]
             assert prop_out['value'] == p[1]

             # check statfs results
             results = POST('/filesystem/statfs/', path)
             assert results.status_code == 200, results.text

             mount_flags = results.json()['flags']
             assert p[2] in mount_flags, f'{path}: ({p[2]}) not in {mount_flags}'
