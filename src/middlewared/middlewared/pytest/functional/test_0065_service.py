import pytest


services = [
    'afp', 'cifs', 'nfs', 'snmp', 'tftp', 'webdav', 'lldp'
]


def test_service_query(conn):
    req = conn.rest.get('service')

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), list) is True


def test_service_update(conn):
    req = conn.rest.get('service')

    assert req.status_code == 200, req.text
    services = req.json()
    assert isinstance(services, list) is True

    for svc in services[:5]:
        req = conn.rest.put(f'service/id/{svc["id"]}', data=[{'enable': svc['enable']}])
        assert req.status_code == 200, req.text


@pytest.mark.parametrize('svc', services)
def test_service_start(conn, svc):

    req = conn.rest.post('service/start', data=[svc])

    assert req.status_code == 200, req.text
    assert req.json() is True


@pytest.mark.parametrize('svc', services)
def test_service_stop(conn, svc):

    req = conn.rest.post('service/stop', data=[svc])

    assert req.status_code == 200, req.text
    assert req.json() is False
