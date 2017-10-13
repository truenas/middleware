import pytest


invalid_users = [['root', '123'], ['test', 'test']]


def test_auth_check_valid_user(conn):
    valid_user = conn.rest.post('auth/check_user', data=['root', 'freenas'])

    assert valid_user.status_code == 200
    assert valid_user.json() is True


@pytest.mark.parametrize('data_user', invalid_users)
def test_auth_check_invalid_user(conn, data_user):
    invalid_user = conn.rest.post('auth/check_user', data=data_user)

    assert invalid_user.status_code == 200
    assert invalid_user.json() is False


@pytest.mark.parametrize('data_random', [[], [1000], [2000], [3000], [4000], [5000]])
def test_generate_token(conn, data_random):
    generate_token = conn.rest.post('auth/generate_token', data=data_random)

    assert generate_token.status_code == 200
    assert isinstance(generate_token.json(), str) is True

    assert conn.ws.call('auth.token', generate_token.json()) is True
