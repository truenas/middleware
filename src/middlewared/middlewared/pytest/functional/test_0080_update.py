def test_update_get_trains(conn):
    req = conn.rest.get('update/get_trains')

    assert req.status_code == 200
    assert isinstance(req.json(), dict) is True


def test_update_check_available(conn):
    req = conn.rest.post('update/check_available')

    assert req.status_code == 200
    assert isinstance(req.json(), dict) is True


def test_update_get_pending(conn):
    req = conn.rest.post('update/get_pending')

    assert req.status_code == 200
    assert isinstance(req.json(), list) is True
