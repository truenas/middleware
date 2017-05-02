import pytest


data = {
    'key1': 'value1',
    'key2': 2,
    'key3': True,
    'key4': 4.0,
}


@pytest.mark.parametrize('kv', list(data.items()))
def test_cache_put(conn, kv):
    key, value = kv
    conn.ws.call('cache.put', key, value)


@pytest.mark.parametrize('kv', list(data.items()))
def test_cache_get(conn, kv):
    key, value = kv
    get = conn.ws.call('cache.get', key)
    assert get == value


@pytest.mark.parametrize('kv', list(data.items()))
def test_cache_has_key(conn, kv):
    key, value = kv
    has_key = conn.ws.call('cache.has_key', key)
    assert has_key is True


def test_cache_has_no_key(conn):
    has_key = conn.ws.call('cache.has_key', 'some_unknown_key')
    assert has_key is False


@pytest.mark.parametrize('kv', list(data.items()))
def test_cache_pop(conn, kv):
    key, value = kv
    pop = conn.ws.call('cache.pop', key)
    assert pop == value
