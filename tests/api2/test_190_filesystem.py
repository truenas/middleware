#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')
path_list = ['kernel', 'mbr', 'zfs', 'modules']
random_path = ['/boot/kernel', '/root', '/bin', '/usr/bin']


def test_01_get_filesystem_listdir():
    results = POST('/filesystem/listdir/', {'path': '/boot'})
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    assert len(results.json()) > 0, results.text
    global listdir
    listdir = results


@pytest.mark.parametrize('name', path_list)
def test_02_looking_at_listdir_path_(name):
    for dline in listdir.json():
        if dline['path'] == f'/boot/{name}':
            assert dline['type'] in ('DIRECTORY', 'FILE'), listdir.text
            assert dline['uid'] == 0, listdir.text
            assert dline['gid'] == 0, listdir.text
            assert dline['name'] == name, listdir.text
            break
    else:
        raise AssertionError('/boot/{name} not found')


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
    assert results.json()['group'] == 'wheel', results.text
    assert results.json()['acl'] is False, results.text
