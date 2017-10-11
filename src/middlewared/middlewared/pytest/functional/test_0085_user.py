import pytest


@pytest.fixture(scope='module')
def data():
    return {}


def test_user_query(conn):
    req = conn.rest.get('user')

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), list) is True


def test_user_get_next_uid(conn):
    req = conn.rest.get('user/get_next_uid')

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), int) is True


def test_user_0100_create(conn, data):
    req = conn.rest.post('user', data={
        'username': 'test555',
        'full_name': 'Test User',
        'password': '12345',
        'group_create': True,
    })

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), int) is True
    data['id'] = req.json()


def test_user_0500_update(conn, data):

    if 'id' not in data:
        pytest.skip('No user id found')

    req = conn.rest.put(f'user/id/{data["id"]}', data={
        'full_name': 'Test User Update',
    })

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), int) is True


def test_user_0900_delete(conn, data):

    if 'id' not in data:
        pytest.skip('No user id found')

    req = conn.rest.delete(f'user/id/{data["id"]}')

    assert req.status_code == 200, req.text
