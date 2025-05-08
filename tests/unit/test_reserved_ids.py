import pytest
from middlewared.utils import reserved_ids
from threading import Lock
from time import monotonic
from truenas_api_client import Client


@pytest.fixture(scope='function')
def reserve_obj():
    return reserved_ids.ReservedXid({}, Lock())


def test_add_entry(reserve_obj):
    reserve_obj.add_entry(865)
    assert not reserve_obj.available(865)
    assert 865 in reserve_obj.in_use()


def test_remove_entry(reserve_obj):
    reserve_obj.add_entry(865)
    assert not reserve_obj.available(865)

    reserve_obj.remove_entry(865)
    assert reserve_obj.available(865)
    assert 865 not in reserve_obj.in_use()


def test_expire_entry(reserve_obj):
    reserve_obj.add_entry(865)
    assert not reserve_obj.available(865)

    reserve_obj.in_flight[865] = monotonic() - reserved_ids.LOCKED_XID_TTL - 1
    assert reserve_obj.available(865)
    assert 865 not in reserve_obj.in_use()


@pytest.mark.parametrize('method,minimum', [
    ('user.get_next_uid', 3000),
    ('group.get_next_gid', 3000),
])
def test_check_increment_method(method, minimum):
    with Client() as c:
        xid = c.call(method)
        assert xid == minimum

        xid = c.call(method)
        assert xid == minimum + 1
