import pytest


@pytest.mark.parametrize('dtype', ['SERIAL'])
def test_get_info(conn, dtype):
    config = conn.rest.post('device/get_info', data=[dtype])

    assert config.status_code == 200
    assert isinstance(config.json(), list) is True
