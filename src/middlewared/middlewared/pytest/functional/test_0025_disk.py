def test_disk_query(conn):
    req = conn.rest.get('disk')

    assert req.status_code == 200
    assert isinstance(req.json(), list) is True
