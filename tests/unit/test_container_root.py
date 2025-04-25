import os
import pytest

from truenas_api_client import Client
from middlewared.plugins.account_.constants import SYNTHETIC_CONTAINER_ROOT


def test__query_by_name():
    with Client() as c:
        entry = c.call('user.query', [['username', '=', SYNTHETIC_CONTAINER_ROOT['pw_name']]], {'get': True})
        assert entry['local']
        assert entry['builtin']
        assert entry['uid'] == SYNTHETIC_CONTAINER_ROOT['pw_uid']


def test__query_by_id():
    with Client() as c:
        entry = c.call('user.query', [['uid', '=', SYNTHETIC_CONTAINER_ROOT['pw_uid']]], {'get': True})
        assert entry['local']
        assert entry['builtin']
        assert entry['username'] == SYNTHETIC_CONTAINER_ROOT['pw_name']


def test__user_obj_by_name():
    with Client() as c:
        obj = c.call('user.get_user_obj', {'username': SYNTHETIC_CONTAINER_ROOT['pw_name']})
        assert obj == SYNTHETIC_CONTAINER_ROOT


def test__user_obj_by_uid():
    with Client() as c:
        obj = c.call('user.get_user_obj', {'uid': SYNTHETIC_CONTAINER_ROOT['pw_uid']})
        assert obj == SYNTHETIC_CONTAINER_ROOT


def test__user_obj_stat():
    DIR = '/tmp/container_root_stat_test'
    os.mkdir(DIR)
    os.chown(DIR, SYNTHETIC_CONTAINER_ROOT['pw_uid'], 0)
    with Client() as c:
        st = c.call('filesystem.stat', DIR)
        assert st['user'] == SYNTHETIC_CONTAINER_ROOT['pw_name']


@pytest.mark.parametrize('file', ['/etc/shadow', '/etc/passwd'])
def test__no_sythentic_entry(file):
    with open(file, 'r') as f:
        data = f.read()
        assert SYNTHETIC_CONTAINER_ROOT['pw_name'] not in data
