def test_core_get_services(conn):
    req = conn.rest.get('core/get_services')

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), dict) is True


def test_core_get_methods(conn):
    req = conn.rest.post('core/get_methods')

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), dict) is True


def test_core_get_jobs(conn):
    req = conn.rest.get('core/get_jobs')

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), list) is True


def test_core_ping(conn):
    req = conn.rest.get('core/ping')

    assert req.status_code == 200, req.text
    assert req.json() == 'pong'
