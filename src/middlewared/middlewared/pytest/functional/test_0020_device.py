import pytest


@pytest.mark.parametrize('dtype', ['SERIAL', 'DISK'])
def test_device_get_info(conn, dtype):
    req = conn.rest.post('device/get_info', data=dtype)

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), (list, dict)) is True
