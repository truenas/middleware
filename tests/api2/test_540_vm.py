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

bootloader = {'UEFI': 'UEFI', 'UEFI_CSM': 'Legacy BIOS'}


@pytest.fixture(scope='module')
def data():
    return {}


def test_01_looking_vm_flags():
    results = GET('/vm/flags/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text


@pytest.mark.parametrize('dkey', list(bootloader.keys()))
def test_02_verify_vm_bootloader_options(dkey):
    results = GET('/vm/bootloader_options/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    assert bootloader[dkey] == results.json()[dkey]


def test_03_get_available_memory_for_vms(data):
    results = POST('/vm/get_available_memory/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text


# /vm/guest_architecture_and_machine_choices


# Only run if the system support virtualization
if support_virtualization:

    def test_04_creating_vm(data):
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

    def test_05_get_vm_query(data):
        results = GET(f'/vm/?id={data["vmid"]}')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list) is True, results.text
        global vmware_query
        vmware_query = results

    @pytest.mark.parametrize('dkey', ['name', 'description', 'vcpus', 'memory',
                                      'bootloader', 'autostart'])
    def test_06_look_vm_query_(dkey):
        assert vmware_query.json()[0][dkey] == payload[dkey], vmware_query.text

    def test_07_start_vm(data):
        results = POST(f'/vm/id/{data["vmid"]}/start/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), type(None)), results.text

    def test_08_verify_vm_status_is_running(data):
        results = POST(f'/vm/id/{data["vmid"]}/status/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['state'] == 'RUNNING', results.text
        assert isinstance(results.json()['pid'], int), results.text
        assert results.json()['domain_state'] == 'RUNNING', results.text

    def test_09_get_vm_console_name(data):
        results = POST('/vm/get_console/', data['vmid'])
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), str), results.text
        assert results.json() == f'{data["vmid"]}_vmtest'

    def test_10_get_vm_memory_usage():
        results = POST('/vm/get_memory_usage/', data["vmid"])
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text

    def test_11_get_vm_memory_info_on_started_vm():
        results = POST('/vm/get_memory_usage/', data["vmid"])
        assert results.status_code == 422, results.text
        assert isinstance(results.json(), dict), results.text
        assert 'get_vm_memory_info' in results.json()['message']

    @pytest.mark.parametrize('dkey', ['RNP', 'PRD', 'RPRD'])
    def test_12_verify_vm_bootloader_options(dkey):
        results = GET('/vm/get_vmemory_in_use/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert isinstance(results.json()[dkey], int), results.text

    def test_13_stop_vm(data):
        results = POST(f'/vm/id/{data["vmid"]}/stop/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 180)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_14_verify_vm_status_is_stopped(data):
        results = POST(f'/vm/id/{data["vmid"]}/status/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['state'] == 'STOPPED', results.text
        assert isinstance(results.json()['pid'], type(None)), results.text
        assert results.json()['domain_state'] == 'SHUTOFF', results.text

    def test_15_update_vm(data):
        global payload
        payload = {
            'memory': 768,
        }
        results = PUT(f'/vm/id/{data["vmid"]}/', payload)
        assert results.status_code == 200, results.text
        assert GET(f'/vm?id={data["vmid"]}').json()[0]['memory'] == 768

    @pytest.mark.parametrize('dkey', ['memory'])
    def test_16_get_vm_query(data, dkey):
        results = GET(f'/vm/id/{data["vmid"]}')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict) is True, results.text
        assert results.json()[dkey] == payload[dkey], results.text

    def test_17_clone_a_vm(data):
        results = POST(f'/vm/id/{data["vmid"]}/clone/', 'vmtest2')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), bool) is True, results.text
        data['vmid2'] = GET('/vm/?name=vmtest2').json()[0]['id']

    def test_18_get_the_clone_vm_console_name(data):
        results = POST('/vm/get_console/', data['vmid2'])
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), str), results.text
        assert results.json() == f'{data["vmid2"]}_vmtest2'

    def test_18_get_vm_memory_info_on_stopped_vm(data):
        results = POST('/vm/get_memory_usage/', data["vmid2"])
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    @pytest.mark.parametrize('vmid', ['vmid', 'vmid2'])
    def test_20_delete_vms(data, vmid):
        results = DELETE(f'/vm/id/{data[vmid]}/')
        assert results.status_code == 200, results.text


def test_30_vm_disk_choices(request):
    with dataset('test zvol', {
        'type': 'VOLUME',
        'volsize': 1024000,
    }) as ds:
        results = GET('/vm/device/disk_choices')
        assert isinstance(results.json(), dict) is True
        assert results.json().get(f'/dev/zvol/{ds.replace(" ", "+")}') == f'{ds}'
