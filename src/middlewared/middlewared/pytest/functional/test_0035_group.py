import pytest


@pytest.fixture(scope='module')
def data():
    return {}


def test_group_query(conn):
    req = conn.rest.get('group')

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), list) is True


def test_group_get_next_gid(conn):
    req = conn.rest.get('group/get_next_gid')

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), int) is True


def test_group_0100_create(conn, data):
    req = conn.rest.post('group', data={
        'name': 'gtest555',
    })

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), int) is True
    data['id'] = req.json()


def test_group_0500_update(conn, data):

    if 'id' not in data:
        pytest.skip('No group id found')

    req = conn.rest.put(f'group/id/{data["id"]}', data={
        'sudo': True,
    })

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), int) is True


def test_group_0900_delete(conn, data):

    if 'id' not in data:
        pytest.skip('No group id found')

    req = conn.rest.delete(f'group/id/{data["id"]}')

    assert req.status_code == 200, req.text
