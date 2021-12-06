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


@pytest.mark.parametrize('pool', pool_name)
def test_04_test_filesystem_statfs_fstype(pool):
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


@pytest.mark.parametrize('pool', pool_name)
def test_05_set_immutable_flag_on_path(pool):
    t_path = os.path.join('/mnt', pool, 'random_directory_immutable')
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
