#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST


def test_01_get_filesystem_listdir():
    results = POST('/filesystem/listdir/', {'path': '/boot'})
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    assert len(results.json()) > 0, results.text
    global listdir
    listdir = results


@pytest.mark.parametrize('name', ['kernel', 'mbr', 'zfs', 'modules'])
def test_02_looking_at_listdir_path_(name):
    for dline in listdir.json():
        if dline['path'] == f'/boot/{name}':
            assert dline['type'] in ('DIRECTORY', 'FILE'), listdir.text
            assert dline['uid'] == 0, listdir.text
            assert dline['gid'] == 0, listdir.text
            assert dline['name'] == name, listdir.text
            break
    else:
        raise AssertionError(f'/boot/{name} not found')


@pytest.mark.parametrize('path', ['/boot/kernel', '/root', '/bin', '/usr/bin'])
def test_03_get_filesystem_stat_(path):
    results = POST('/filesystem/stat/', path)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.test
    assert isinstance(results.json()['size'], int) is True, results.test
    assert isinstance(results.json()['mode'], int) is True, results.test
    assert results.json()['uid'] == 0, results.test
    assert results.json()['gid'] == 0, results.test
    assert isinstance(results.json()['atime'], float) is True, results.test
    assert isinstance(results.json()['mtime'], float) is True, results.test
    assert isinstance(results.json()['ctime'], float) is True, results.test
    assert isinstance(results.json()['dev'], int) is True, results.test
    assert isinstance(results.json()['inode'], int) is True, results.test
    assert results.json()['nlink'] in (2, 3), results.test
    assert results.json()['user'] == 'root', results.test
    assert results.json()['group'] == 'wheel', results.test
    assert results.json()['acl'] == 'unix', results.test
