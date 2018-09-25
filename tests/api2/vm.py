#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT, DELETE

global vmware_query
vmware_query = None


@pytest.fixture(scope='module')
def data():
    return {}


def test_01_looking_vm_flags():
    results = GET('/vm/flags/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True


def test_02_creating_vm(data):
    payload = {
        'name': 'vmtest',
        'description': 'desc',
        'vcpus': 1,
        'memory': 1000,
        'bootloader': 'UEFI',
        'devices': [],
        'autostart': False,
    }
    results = POST('/vm/', payload)
    assert results.status_code == 200, results.text
    data['vmid'] = results.json()


def test_03_get_vm_query(data):
    results = GET(f'/vm/?id={data["vmid"]}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    global vmware_query
    vmware_query = results


def test_04_look_vm_name_query():
    assert vmware_query.json()[0]['name'] == 'vmtest', vmware_query.text


def test_05_look_vm__description_query():
    assert vmware_query.json()[0]['description'] == 'desc', vmware_query.text


def test_06_look_vm_vcpus_query():
    assert vmware_query.json()[0]['vcpus'] == 1, vmware_query.text


def test_07_look_vm_memory_query():
    assert vmware_query.json()[0]['memory'] == 1000, vmware_query.text


def test_08_look_vm_bootloader_query():
    assert vmware_query.json()[0]['bootloader'] == 'UEFI', vmware_query.text


def test_09_look_vm_devices_query():
    assert vmware_query.json()[0]['devices'] == [], vmware_query.text


def test_10_look_vm_autostart_query():
    assert vmware_query.json()[0]['autostart'] == False, vmware_query.text


@pytest.mark.skip('Not working in Bhyve')
def test_11_start_vm(data):
    results = POST(f'/vm/id/{data["vmid"]}/start/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True


def test_12_vm_status(data):
    results = POST(f'/vm/id/{data["vmid"]}/status/')
    assert results.status_code == 200, results.text
    status = results.json()
    assert isinstance(status, dict) is True


def test_13_stop_vm(data):
    results = POST(f'/vm/id/{data["vmid"]}/stop/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True


def test_14_update_vm(data):
    payload = {
        'memory': 1100,
    }
    results = PUT(f'/vm/id/{data["vmid"]}/', payload)
    assert results.status_code == 200, results.text
    assert GET(f'/vm?id={data["vmid"]}').json()[0]['memory'] == 1100


def test_15_get_vm_query(data):
    results = GET(f'/vm/?id={data["vmid"]}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    global vmware_query
    vmware_query = results


def test_16_look_vm_memory_query():
    assert vmware_query.json()[0]['memory'] == 1100, vmware_query.text


def test_17_delete_vm(data):
    results = DELETE(f'/vm/id/{data["vmid"]}/')
    assert results.status_code == 200, results.text
