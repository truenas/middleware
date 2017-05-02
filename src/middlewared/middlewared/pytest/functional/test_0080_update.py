def test_get_trains(conn):
    req = conn.rest.get('update/get_trains')

    assert req.status_code == 200
    assert isinstance(req.json(), dict) is True
