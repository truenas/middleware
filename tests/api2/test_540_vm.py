#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT, DELETE, wait_on_job
from auto_config import dev_test, ha
from middlewared.test.integration.assets.pool import dataset

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for development testing')

global vmware_query, real_device
vmware_query = None
message = "This system does not support virtualization."
payload = {
    'name': 'nested_vm',
    'memory': 250,
    'autostart': False,
}
results = POST('/vm/', payload, controller_a=ha)
support_virtualization = False if message in results.text else True


@pytest.fixture(scope='module')
def data():
    return {}


def test_01_looking_vm_flags():
    results = GET('/vm/flags/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text


# Only run if the system support virtualization
if support_virtualization:
    def test_02_creating_vm(data):
        global payload
        payload = {
            'name': 'vmtest',
            'description': 'desc',
            'vcpus': 1,
            'memory': 512,
            'bootloader': 'UEFI',
            'autostart': False,
        }
        results = POST('/vm/', payload)
        assert results.status_code == 200, results.text
        data['vmid'] = results.json()['id']

    def test_03_get_vm_query(data):
        results = GET(f'/vm/?id={data["vmid"]}')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list) is True, results.text
        global vmware_query
        vmware_query = results

    @pytest.mark.parametrize('dkey', ['name', 'description', 'vcpus', 'memory',
                                      'bootloader', 'autostart'])
    def test_04_look_vm_query_(dkey):
        assert vmware_query.json()[0][dkey] == payload[dkey], vmware_query.text

    def test_05_start_vm(data):
        results = POST(f'/vm/id/{data["vmid"]}/start/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), type(None)), results.text

    def test_06_vm_status(data):
        results = POST(f'/vm/id/{data["vmid"]}/status/')
        assert results.status_code == 200, results.text
        status = results.json()
        assert isinstance(status, dict), results.text

    def test_07_stop_vm(data):
        results = POST(f'/vm/id/{data["vmid"]}/stop/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 180)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_08_update_vm(data):
        global payload
        payload = {
            'memory': 768,
        }
        results = PUT(f'/vm/id/{data["vmid"]}/', payload)
        assert results.status_code == 200, results.text
        assert GET(f'/vm?id={data["vmid"]}').json()[0]['memory'] == 768

    def test_09_get_vm_query(data):
        results = GET(f'/vm/?id={data["vmid"]}')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list) is True, results.text
        global vmware_query
        vmware_query = results

    @pytest.mark.parametrize('dkey', ['memory'])
    def test_10_look_vm_query_(dkey):
        assert vmware_query.json()[0][dkey] == payload[dkey], vmware_query.text

    def test_11_delete_vm(data):
        results = DELETE(f'/vm/id/{data["vmid"]}/')
        assert results.status_code == 200, results.text


def test_12_vm_disk_choices(request):
    with dataset('test zvol', {
        'type': 'VOLUME',
        'volsize': 1024000,
    }) as ds:
        results = GET('/vm/device/disk_choices')
        assert isinstance(results.json(), dict) is True
        assert results.json().get(f'/dev/zvol/{ds.replace(" ", "+")}') == f'{ds}'
