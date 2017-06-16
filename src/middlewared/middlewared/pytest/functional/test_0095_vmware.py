import os
import pytest


def _check():
    if (
        'VMWARE_HOST' not in os.environ or
        'VMWARE_USERNAME' not in os.environ or
        'VMWARE_PASSWORD' not in os.environ
    ):
        pytest.skip("No credentials")


@pytest.fixture(scope='module')
def creds():
    return {}


def test_vmware_query(conn):
    req = conn.rest.get('vmware')
    assert req.status_code == 200
    assert isinstance(req.json(), list) is True


def test_vmware_get_datastores(conn, creds):
    _check()
    req = conn.rest.post('vmware/get_datastores', data=[{
        'hostname': os.environ['VMWARE_HOST'],
        'username': os.environ['VMWARE_USERNAME'],
        'password': os.environ['VMWARE_PASSWORD'],
    }])
    assert req.status_code == 200
    datastores = req.json()
    assert isinstance(datastores, dict) is True
    assert len(datastores) > 0
