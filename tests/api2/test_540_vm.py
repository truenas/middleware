#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT, DELETE, wait_on_job
from auto_config import dev_test, ha

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for development testing')

support_virtualization = GET('/vm/supports_virtualization/', controller_a=ha).json()

bootloader = {'UEFI': 'UEFI', 'UEFI_CSM': 'Legacy BIOS'}


@pytest.fixture(scope='module')
def data():
    return {}


def test_01_verify_machine_supports_virtualization():
    results = GET('/vm/supports_virtualization/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool), results.text


def test_02_get_virtualization_details():
    results = GET('/vm/virtualization_details/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert isinstance(results.json()['supported'], bool), results.text


def test_03_get_vm_flags():
    results = GET('/vm/flags/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_04_get_vm_cpu_model_choices():
    results = GET('/vm/cpu_model_choices/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['EPYC'] == 'EPYC', results.json()


# Only run if the system support virtualization
if support_virtualization:

    @pytest.mark.parametrize('dkey', list(bootloader.keys()))
    def test_05_verify_vm_bootloader_options(dkey):
        results = GET('/vm/bootloader_options/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert bootloader[dkey] == results.json()[dkey]

    def test_06_get_available_memory_for_vms(data):
        results = POST('/vm/get_available_memory/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text

    # /vm/guest_architecture_and_machine_choices
    @pytest.mark.parametrize('dkey', ['i686', 'x86_64'])
    def test_07_verify_vm_guest_architecture_and_machine_choices(dkey):
        results = GET('/vm/guest_architecture_and_machine_choices/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert isinstance(results.json()[dkey], list), results.text

    def test_08_verify_maximum_supported_vcpus():
        results = GET('/vm/maximum_supported_vcpus/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text

    @pytest.mark.parametrize('dkey', ['port', 'web'])
    def test_09_get_vm_port_wizard(dkey):
        results = GET('/vm/port_wizard/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert isinstance(results.json()[dkey], int), results.text

    def test_10_get_random_mac():
        results = GET('/vm/random_mac/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), str), results.text

    def test_12_get_resolution_choices():
        results = GET('/vm/resolution_choices/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['1920x1080'] == '1920x1080', results.text

    def test_13_creating_vm(data):
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

    def test_13_get_vm_query(data):
        results = GET(f'/vm/?id={data["vmid"]}')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text
        global vmware_query
        vmware_query = results

    @pytest.mark.parametrize('dkey', ['name', 'description', 'vcpus', 'memory',
                                      'bootloader', 'autostart'])
    def test_14_look_vm_query_(dkey):
        assert vmware_query.json()[0][dkey] == payload[dkey], vmware_query.text

    def test_15_start_vm(data):
        results = POST(f'/vm/id/{data["vmid"]}/start/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), type(None)), results.text

    def test_16_verify_vm_status_is_running(data):
        results = POST(f'/vm/id/{data["vmid"]}/status/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['state'] == 'RUNNING', results.text
        assert isinstance(results.json()['pid'], int), results.text
        assert results.json()['domain_state'] == 'RUNNING', results.text

    def test_17_get_vm_console_name(data):
        results = POST('/vm/get_console/', data['vmid'])
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), str), results.text
        assert results.json() == f'{data["vmid"]}_vmtest'

    def test_18_get_vm_memory_usage(data):
        results = POST('/vm/get_memory_usage/', data["vmid"])
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text

    def test_19_get_vm_memory_info_on_started_vm(data):
        results = POST('/vm/get_memory_usage/', data["vmid"])
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text

    def test_20_get_vm_log_file_path(data):
        results = POST('/vm/log_file_path/', data["vmid"])
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), str), results.text
        assert f'{data["vmid"]}_vmtest' in results.json()

    @pytest.mark.parametrize('dkey', ['RNP', 'PRD', 'RPRD'])
    def test_21_verify_vm_bootloader_options(dkey):
        results = GET('/vm/get_vmemory_in_use/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert isinstance(results.json()[dkey], int), results.text

    def test_22_suspend_vm(data):
        results = POST(f'/vm/id/{data["vmid"]}/suspend')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), type(None)), results.text
        sleep(1)

    def test_23_verify_vm_status_is_suspended(data):
        results = POST(f'/vm/id/{data["vmid"]}/status/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['state'] == 'SUSPENDED', results.text
        assert isinstance(results.json()['pid'], int), results.text
        assert results.json()['domain_state'] == 'PAUSED', results.text

    def test_24_resume_vm(data):
        results = POST(f'/vm/id/{data["vmid"]}/resume')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), type(None)), results.text
        sleep(1)

    def test_25_verify_vm_status_is_running_after_resuming(data):
        results = POST(f'/vm/id/{data["vmid"]}/status/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['state'] == 'RUNNING', results.text
        assert isinstance(results.json()['pid'], int), results.text
        assert results.json()['domain_state'] == 'RUNNING', results.text

    def test_26_restart_vm(data):
        results = POST(f'/vm/id/{data["vmid"]}/restart')
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 180)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        sleep(1)

    def test_27_verify_vm_status_is_running_after_restarting(data):
        results = POST(f'/vm/id/{data["vmid"]}/status/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['state'] == 'RUNNING', results.text
        assert isinstance(results.json()['pid'], int), results.text
        assert results.json()['domain_state'] == 'RUNNING', results.text

    def test_28_stop_vm(data):
        results = POST(f'/vm/id/{data["vmid"]}/stop/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 180)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_29_poweroff_vm(data):
        results = POST(f'/vm/id/{data["vmid"]}/poweroff/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), type(None)), results.text
        sleep(1)

    def test_30_verify_vm_status_is_stopped_and_shutoff(data):
        results = POST(f'/vm/id/{data["vmid"]}/status/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['state'] == 'STOPPED', results.text
        assert isinstance(results.json()['pid'], type(None)), results.text
        assert results.json()['domain_state'] == 'SHUTOFF', results.text

    def test_31_update_vm(data):
        global payload
        payload = {
            'memory': 768,
        }
        results = PUT(f'/vm/id/{data["vmid"]}/', payload)
        assert results.status_code == 200, results.text
        assert GET(f'/vm?id={data["vmid"]}').json()[0]['memory'] == 768

    @pytest.mark.parametrize('dkey', ['memory'])
    def test_32_get_vm_query(data, dkey):
        results = GET(f'/vm/id/{data["vmid"]}')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()[dkey] == payload[dkey], results.text

    def test_33_clone_a_vm(data):
        results = POST(f'/vm/id/{data["vmid"]}/clone/', 'vmtest2')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), bool), results.text
        data['vmid2'] = GET('/vm/?name=vmtest2').json()[0]['id']

    def test_34_verify_cloned_vm_status_is_stopped(data):
        results = POST(f'/vm/id/{data["vmid2"]}/status/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['state'] == 'STOPPED', results.text
        assert isinstance(results.json()['pid'], type(None)), results.text
        assert results.json()['domain_state'] == 'SHUTOFF', results.text

    def test_35_get_the_clone_vm_console_name(data):
        results = POST('/vm/get_console/', data['vmid2'])
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), str), results.text
        assert results.json() == f'{data["vmid2"]}_vmtest2'

    def test_36_get_vm_memory_info_on_stopped_vm(data):
        results = POST('/vm/get_memory_usage/', data["vmid2"])
        assert results.status_code == 422, results.text
        assert isinstance(results.json(), dict), results.text

    @pytest.mark.parametrize('vmid', ['vmid', 'vmid2'])
    def test_37_delete_vms(data, vmid):
        results = DELETE(f'/vm/id/{data[vmid]}/')
        assert results.status_code == 200, results.text
