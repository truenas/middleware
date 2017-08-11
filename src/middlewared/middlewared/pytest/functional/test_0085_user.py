def test_user_query(conn):
    req = conn.rest.get('user')

    assert req.status_code == 200
    assert isinstance(req.json(), list) is True
