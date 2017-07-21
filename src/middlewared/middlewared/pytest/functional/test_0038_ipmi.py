import pytest

def check_ipmi(conn):
    if not conn.ws.call('ipmi.is_loaded'):
        pytest.skip('No IPMI found')


def test_ipmi_channels(conn):
    check_ipmi(conn)

    req = conn.rest.get('ipmi/channels')

    assert req.status_code == 200
    assert isinstance(req.json(), list) is True
