import contextlib
import pytest

from middlewared.test.integration.assets.pool import dataset, pool
from middlewared.test.integration.utils import call, ssh

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
pytestmark = pytest.mark.rbac


@contextlib.contextmanager
def file(name, user, group, permissions):
    with dataset('test_perms', pool=pool) as test_dataset:
        path = os.path.join('/mnt', test_dataset, name)
        with file_at_path(path, user, group, permissions):
            yield path


@contextlib.contextmanager
def file_at_path(path, user, group, permissions):
    ssh(f'install -o {user} -g {group} -m {permissions} /dev/null {path}')
    try:
        yield path
    finally:
        ssh(f'rm -f {path}')


@contextlib.contextmanager
def directory(name, user, group, permissions):
    with dataset('test_perms', pool=pool) as test_dataset:
        path = os.path.join('/mnt', test_dataset, name)
        ssh(f'mkdir -p -m {permissions} {path}')
        ssh(f'chown -R {user}:{group} {path}')

        try:
            yield path
        finally:
            ssh(f'rm -rf {path}')


def test_non_authorized_user_access():
    with file('test', 'root', 'root', '700') as file_path:
        for perm_check in ('read', 'write', 'execute'):
            assert call('filesystem.can_access_as_user', 'nobody', file_path, {perm_check: True}) is False


def test_authorized_user_access():
    for user, group in (('apps', 'apps'), ('nobody', 'nogroup')):
        with file('test', user, group, '700') as file_path:
            for perm_check in ('read', 'write', 'execute'):
                assert call('filesystem.can_access_as_user', user, file_path, {perm_check: True}) is True


def test_read_access():
    for user, group in (('apps', 'apps'), ('nobody', 'nogroup')):
        with file('test', user, group, '400') as file_path:
            for perm_check, value in (('read', True), ('write', False), ('execute', False)):
                assert call('filesystem.can_access_as_user', user, file_path, {perm_check: True}) is value


def test_write_access():
    for user, group in (('apps', 'apps'), ('nobody', 'nogroup')):
        with file('test', user, group, '200') as file_path:
            for perm_check, value in (('read', False), ('write', True), ('execute', False)):
                assert call('filesystem.can_access_as_user', user, file_path, {perm_check: True}) is value


def test_execute_access():
    for user, group in (('apps', 'apps'), ('nobody', 'nogroup')):
        with file('test', user, group, '100') as file_path:
            for perm_check, value in (('read', False), ('write', False), ('execute', True)):
                assert call('filesystem.can_access_as_user', user, file_path, {perm_check: True}) is value


def test_nested_perm_execute_check():
    with directory('test_dir', 'root', 'root', '700') as dir_path:
        file_path = os.path.join(dir_path, 'testfile')
        with file_at_path(file_path, 'root', 'root', '777'):
            assert call('filesystem.can_access_as_user', 'apps', file_path, {'execute': True}) is False
