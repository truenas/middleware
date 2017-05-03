def test_flags(conn):
    req = conn.rest.get('vm/flags')

    assert req.status_code == 200
    assert isinstance(req.json(), dict) is True
