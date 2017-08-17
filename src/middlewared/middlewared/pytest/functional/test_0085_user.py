def test_user_query(conn):
    req = conn.rest.get('user')

    assert req.status_code == 200
    assert isinstance(req.json(), list) is True


def test_user_0100_create(conn):
    req = conn.rest.post('user', data=[{
        'username': 'test555',
        'full_name': 'Test User',
        'password': '12345',
        'group': 1,
    }])

    assert req.status_code == 200
