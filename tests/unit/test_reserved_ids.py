import pytest
from middlewared.utils import reserved_ids
from multiprocessing import Pool
from threading import Lock
from time import monotonic
from truenas_api_client import Client


@pytest.fixture(scope='function')
def reserve_obj():
    return reserved_ids.ReservedXid({})


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


def get_uid():
    with Client() as c:
        return c.call('user.get_next_uid')


def get_gid():
    with Client() as c:
        return c.call('group.get_next_gid')


@pytest.mark.parametrize('method,minimum', [
    (get_uid, 3000),
    (get_gid, 3000),
])
def test_check_increment_method(method, minimum):
    with Pool(4) as pool:
        results = [pool.apply_async(method, ()) for i in range(0, 20)]
        ids = [res.get(timeout=1) for res in results]

    assert min(ids) == minimum
    assert len(set(ids)) == len(ids), 'duplicate ids assigned'
