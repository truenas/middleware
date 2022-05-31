import contextlib
import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import dev_test
reason = 'Skip for testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


@contextlib.contextmanager
def file(name, user, group, permissions):
    with dataset('test_perms', pool='evo') as test_dataset:
        path = os.path.join('/mnt', test_dataset, name)
        ssh(f'install -o {user} -g {group} -m {permissions} /dev/null {path}')

        try:
            yield path
        finally:
            ssh(f'rm -f {path}')


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
