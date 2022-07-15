import pytest

from config import CLUSTER_IPS
from pytest_dependency import depends
from time import sleep
from utils import make_ws_request


@pytest.mark.dependency(name='CLUSTERCACHE_WORKING')
@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_001_put_get_query_pop(ip, request):
    """
    This validates that all basic operations work
    on all nodes.
    """
    payload_put = {
        'msg': 'method',
        'method': 'clustercache.put',
        'params': ["FOO", {"test": "things"}]
    }
    res = make_ws_request(ip, payload_put)
    assert res.get('error') is None, res

    payload_haskey = {
        'msg': 'method',
        'method': 'clustercache.has_key',
        'params': ["FOO"]
    }
    res = make_ws_request(ip, payload_haskey)
    assert res.get('error') is None, res
    assert res['result'] is True

    payload_get = {
        'msg': 'method',
        'method': 'clustercache.get',
        'params': ["FOO"]
    }
    res = make_ws_request(ip, payload_get)
    assert res.get('error') is None, res
    assert res['result'] == {"test": "things"}

    payload_query = {
        'msg': 'method',
        'method': 'clustercache.query',
        'params': [[['key', '=', 'FOO']]]
    }
    res = make_ws_request(ip, payload_query)
    assert res.get('error') is None, res
    assert len(res['result']) == 1

    payload_pop = {
        'msg': 'method',
        'method': 'clustercache.pop',
        'params': ["FOO"]
    }
    res = make_ws_request(ip, payload_pop)
    assert res.get('error') is None, res
    assert res['result'] == {"test": "things"}

    payload_haskey = {
        'msg': 'method',
        'method': 'clustercache.has_key',
        'params': ["FOO"]
    }
    res = make_ws_request(ip, payload_haskey)
    assert res.get('error') is None, res
    assert res['result'] is False


def test_002_expired_timed_request(request):
    """
    Expired entries should be visible in `has_key`
    but raise exception and remove entry on `get`.
    """
    depends(request, ['CLUSTERCACHE_WORKING'])
    ip = CLUSTER_IPS[0]

    payload_put = {
        'msg': 'method',
        'method': 'clustercache.put',
        'params': ["TEST_ENTRY_TIMED", {"test": "things"}, 3]
    }
    res = make_ws_request(ip, payload_put)
    assert res.get('error') is None, res

    sleep(5)

    payload_haskey = {
        'msg': 'method',
        'method': 'clustercache.has_key',
        'params': ['TEST_ENTRY_TIMED']
    }
    res = make_ws_request(ip, payload_haskey)
    assert res.get('error') is None, res
    assert res['result'] is True

    payload_get = {
        'msg': 'method',
        'method': 'clustercache.get',
        'params': ['TEST_ENTRY_TIMED']
    }
    res = make_ws_request(ip, payload_get)
    assert res.get('error') is not None, res
    assert 'has expired' in res['error']['reason'], res

    payload_haskey = {
        'msg': 'method',
        'method': 'clustercache.has_key',
        'params': ['TEST_ENTRY_TIMED']
    }
    res = make_ws_request(ip, payload_haskey)
    assert res.get('error') is None, res
    assert res['result'] is False


def test_003_create_flag(request):
    """
    clustercache.put should fail with KeyError
    if CREATE specified and entry already exists.
    After failing, check that original
    entry exists with correct value.
    """
    depends(request, ['CLUSTERCACHE_WORKING'])
    ip = CLUSTER_IPS[0]

    payload_put = {
        'msg': 'method',
        'method': 'clustercache.put',
        'params': [
            'TEST_ENTRY_CREATE',
            {'test': 'things'},
            0,
            {'flag': 'CREATE'}
        ]
    }
    res = make_ws_request(ip, payload_put)
    assert res.get('error') is None, res

    payload_put = {
        'msg': 'method',
        'method': 'clustercache.put',
        'params': [
            'TEST_ENTRY_CREATE',
            {'test': 'things2'},
            0,
            {'flag': 'CREATE'}
        ]
    }
    res = make_ws_request(ip, payload_put)
    assert res.get('error') is not None, res

    payload_pop = {
        'msg': 'method',
        'method': 'clustercache.pop',
        'params': ['TEST_ENTRY_CREATE']
    }
    res = make_ws_request(ip, payload_pop)
    assert res.get('error') is None, res
    assert res['result'] == {'test': 'things'}


def test_004_update_flag(request):
    """
    clustercache.put should fail with KeyError
    if UPDATE specied and entry does not exist.
    """
    depends(request, ['CLUSTERCACHE_WORKING'])
    ip = CLUSTER_IPS[0]

    payload_put = {
        'msg': 'method',
        'method': 'clustercache.put',
        'params': [
            'TEST_ENTRY_UPDATE',
            {'test': 'things'},
            0,
            {'flag': 'UPDATE'}
        ]
    }
    res = make_ws_request(ip, payload_put)
    assert res.get('error') is not None, res


@pytest.mark.dependency(name='PRIVATE_CREATED')
def test_005_create_private_entry(request):
    """
    Private entries are encrypted before being written / sent
    of the wire. Middlewared transparently decrypts.
    This test creates the private entry that will be
    checked in subsequent tests.
    """
    depends(request, ['CLUSTERCACHE_WORKING'])
    ip = CLUSTER_IPS[0]

    payload_put = {
        'msg': 'method',
        'method': 'clustercache.put',
        'params': [
            'TEST_ENTRY_PRIVATE',
            {'test': 'things'},
            0,
            {'private': True}
        ]
    }
    res = make_ws_request(ip, payload_put)
    assert res.get('error') is None, res


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_006_create_private_entry(ip, request):
    """
    All nodes should be able to read data and see
    entry as private
    """
    depends(request, ['PRIVATE_CREATED'])

    payload_query = {
        'msg': 'method',
        'method': 'clustercache.query',
        'params': [
            [['key', '=', 'TEST_ENTRY_PRIVATE']],
            {'get': True}
        ]
    }
    res = make_ws_request(ip, payload_query)
    assert res.get('error') is None, res

    assert res['result']['value'] == {'test': 'things'}, res
    assert res['result']['private'] is True, res


def test_007_remove_private_entry(request):
    depends(request, ['PRIVATE_CREATED'])
    ip = CLUSTER_IPS[0]

    payload_pop = {
        'msg': 'method',
        'method': 'clustercache.pop',
        'params': ['TEST_ENTRY_PRIVATE']
    }
    res = make_ws_request(ip, payload_pop)
    assert res.get('error') is None, res
    assert res['result'] == {'test': 'things'}
