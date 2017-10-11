import pytest


def test_consul_fake_alert(conn):
    fake = conn.ws.call('consul.create_fake_alert')
    assert fake is True

    fake = conn.ws.call('consul.remove_fake_alert')
    assert fake is True


@pytest.mark.parametrize('kv', [
    ('foo', 'bar'),
    ('bool', True),
    ('number', 50),
    ('float', 2.5),
])
def test_consul_kv_set_get_delete(conn, kv):
    key, value = kv
    req = conn.rest.post('consul/set_kv', data={'key': key, 'value': value})
    assert req.status_code == 200, req.text

    req = conn.rest.post('consul/get_kv', data=key)
    assert req.status_code == 200, req.text
    assert req.json() == str(value)

    req = conn.rest.post('consul/delete_kv', data=key)
    assert req.status_code == 200, req.text

    req = conn.rest.post('consul/get_kv', data=key)
    assert req.status_code == 200, req.text
    assert req.json() == ''


#FIXME: call hanging
#def test_consul_reload(conn):
#    assert conn.ws.call('consul.reload') is True
