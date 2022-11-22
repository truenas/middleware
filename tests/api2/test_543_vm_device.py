#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, DELETE
from auto_config import dev_test, ha, pool_name, ip
from middlewared.test.integration.assets.pool import dataset
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for development testing')

support_virtualization = GET('/vm/supports_virtualization/', controller_a=ha).json()
DATASET = f'{pool_name}/disks'
DATASET_URL = DATASET.replace('/', '%2F')
DATASET_PATH = f'/mnt/{DATASET}'


@pytest.fixture(scope='module')
def data():
    return {}


def test_01_vm_disk_choices(request):
    #depends(request, ["pool_04"], scope="session")
    with dataset('test zvol', {'type': 'VOLUME', 'volsize': 1024000}) as ds:
        results = GET('/vm/device/disk_choices')
        assert isinstance(results.json(), dict), results.json()
        assert results.json().get(f'/dev/zvol/{ds.replace(" ", "+")}') == f'{ds}'


# Only run if the system support virtualization
if support_virtualization:
    @pytest.mark.parametrize('bind', ['0.0.0.0', '::', ip])
    def test_02_verify_vm_device_bind_choices(bind):
        results = GET('/vm/device/bind_choices')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()[bind] == bind, results.text

    def test_02_create_dataset_for_disk():
        payload = {
            "name": DATASET,
        }
        results = POST("/pool/dataset/", payload)
        assert results.status_code == 200, results.text

    def test_03_creating_a_vm_for_device_testing(data):
        global payload
        payload = {
            'name': 'devicetest',
            'description': 'desc',
            'vcpus': 1,
            'memory': 512,
            'bootloader': 'UEFI',
            'autostart': False,
        }
        results = POST('/vm/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        data['vmid'] = results.json()['id']

    def test_04_create_a_disk_device(data):
        payload = {
            'dtype': 'DISK',
            'vm': data['vmid'],
            'attributes': {'path': DATASET_PATH}
        }
        results = POST('/vm/device', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        data['disk_id'] = results.json()['id']

    def test_05_create_a_display_device(data):
        payload = {
            'dtype': 'DISPLAY',
            'vm': data['vmid'],
            'attributes': {}
        }
        results = POST('/vm/device', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        data['display_id'] = results.json()['id']

    def test_06_verify_vm_device_list():
        results = GET('/vm/device/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text
        assert len(results.json()) > 0, results.text

    def test_07_get_vm_display_devices(data):
        results = POST('/vm/get_display_devices/', data["vmid"])
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text
        assert results.json()[0]['vm'] == data["vmid"], results.json()

    def test_08_delete_vm(data):
        results = DELETE(f'/vm/id/{data["vmid"]}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), bool), results.text

    def test_20_delete_disk_dataset(request):
        results = DELETE(f"/pool/dataset/id/{DATASET_URL}/")
        assert results.status_code == 200, results.text
