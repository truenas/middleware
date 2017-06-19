import pytest


@pytest.fixture(scope='module')
def data():
    return {}


def test_vm_flags(conn):
    req = conn.rest.get('vm/flags')
    assert req.status_code == 200, req.text
    assert isinstance(req.json(), dict) is True


def test_vm_001_create(conn, data):
    req = conn.rest.post('vm', data=[
        {
            'name': 'vmtest',
            'description': 'desc',
            'vcpus': 1,
            'memory': 1000,
            'bootloader': 'UEFI',
            'devices': [
            ],
            'autostart': False,
        }
    ])
    assert req.status_code == 200, req.text
    data['vmid'] = req.json()


def test_vm_200_query(conn):
    req = conn.rest.get('vm')
    assert req.status_code == 200, req.text
    assert isinstance(req.json(), list) is True


def test_vm_300_start(conn, data):
    req = conn.rest.post(f'vm/id/{data["vmid"]}/start')
    assert req.status_code == 200, req.text
    assert isinstance(req.json(), bool) is True


def test_vm_302_status(conn, data):
    req = conn.rest.post(f'vm/id/{data["vmid"]}/status')
    assert req.status_code == 200, req.text
    status = req.json()
    assert isinstance(status, dict) is True


def test_vm_310_stop(conn, data):
    req = conn.rest.post(f'vm/id/{data["vmid"]}/stop')
    assert req.status_code == 200, req.text
    assert isinstance(req.json(), bool) is True


def test_vm_400_update(conn, data):
    vm = conn.rest.get(f'vm?id={data["vmid"]}').json()[0]
    vm['memory'] = 1100
    vm.pop('id')

    req = conn.rest.put(f'vm/id/{data["vmid"]}', data=[vm])
    assert req.status_code == 200, req.text

    assert conn.rest.get(f'vm?id={data["vmid"]}').json()[0]['memory'] == 1100


def test_vm_900_delete(conn, data):
    req = conn.rest.delete(f'vm/id/{data["vmid"]}')
    assert req.status_code == 200, req.text
