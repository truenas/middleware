def test_group_query(conn):
    req = conn.rest.get('group')

    assert req.status_code == 200
    assert isinstance(req.json(), list) is True
