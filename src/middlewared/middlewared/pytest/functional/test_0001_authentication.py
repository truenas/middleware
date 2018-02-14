import pytest


invalid_users = [
    {'username': 'root', 'password': '123'},
    {'username': 'test', 'password': 'test'},
]


def test_auth_check_valid_user(conn):
    req = conn.rest.post('auth/check_user', data={'username': 'root', 'password': 'freenas'})

    assert req.status_code == 200, req.text
    assert req.json() is True


@pytest.mark.parametrize('data_user', invalid_users)
def test_auth_check_invalid_user(conn, data_user):
    req = conn.rest.post('auth/check_user', data=data_user)

    assert req.status_code == 200, req.text
    assert req.json() is False


@pytest.mark.parametrize('data_random', [None, 1000, 2000, 3000, 4000, 5000])
def test_auth_generate_token(conn, data_random):
    req = conn.rest.post('auth/generate_token', data={'ttl': data_random})

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), str) is True

    assert conn.ws.call('auth.token', req.json()) is True
