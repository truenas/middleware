def test_system_version(conn):
    version = conn.rest.get('system/version')

    assert version.status_code == 200, req.text
    assert isinstance(version.json(), str) is True


def test_system_info(conn):
    info = conn.rest.get('system/info')
    assert info.status_code == 200, req.text
    assert isinstance(info.json(), dict) is True


def test_system_ready(conn):
    req = conn.rest.get('system/ready')
    assert req.status_code == 200, req.text
    assert isinstance(req.json(), bool) is True


def test_system_is_freenas(conn):
    r = conn.ws.call('system.is_freenas')
    assert isinstance(r, bool) is True
