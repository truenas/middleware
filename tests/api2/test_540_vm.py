#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT, DELETE
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

global vmware_query
vmware_query = None


@pytest.fixture(scope='module')
def data():
    return {}


def test_01_looking_vm_flags():
    results = GET('/vm/flags/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text


def test_02_creating_vm(data):
    global nested_vm, message
    message = "This system does not support virtualization."
    global payload
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
    if results.status_code == 422 and message in results.text:
        nested_vm = False
        pytest.skip(message)
    else:
        nested_vm = True
        assert results.status_code == 200, results.text
        data['vmid'] = results.json()


def test_03_get_vm_query(data):
    if nested_vm is False:
        pytest.skip(message)
    else:
        results = GET(f'/vm/?id={data["vmid"]}')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list) is True, results.text
        global vmware_query
        vmware_query = results


@pytest.mark.parametrize('dkey', ['name', 'description', 'vcpus', 'memory',
                                  'bootloader', 'devices', 'autostart'])
def test_04_look_vm_query_(dkey):
    if nested_vm is False:
        pytest.skip(message)
    else:
        assert vmware_query.json()[0][dkey] == payload[dkey], vmware_query.text


@pytest.mark.skip('Not working in Bhyve')
def test_05_start_vm(data):
    if nested_vm is False:
        pytest.skip(message)
    else:
        results = POST(f'/vm/id/{data["vmid"]}/start/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), bool) is True, results.text


def test_06_vm_status(data):
    if nested_vm is False:
        pytest.skip(message)
    else:
        results = POST(f'/vm/id/{data["vmid"]}/status/')
        assert results.status_code == 200, results.text
        status = results.json()
        assert isinstance(status, dict) is True, results.text


def test_07_stop_vm(data):
    if nested_vm is False:
        pytest.skip(message)
    else:
        results = POST(f'/vm/id/{data["vmid"]}/stop/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), bool) is True, results.text


def test_08_update_vm(data):
    if nested_vm is False:
        pytest.skip(message)
    else:
        global payload
        payload = {
            'memory': 1100,
        }
        results = PUT(f'/vm/id/{data["vmid"]}/', payload)
        assert results.status_code == 200, results.text
        assert GET(f'/vm?id={data["vmid"]}').json()[0]['memory'] == 1100


def test_09_get_vm_query(data):
    if nested_vm is False:
        pytest.skip(message)
    else:
        results = GET(f'/vm/?id={data["vmid"]}')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list) is True, results.text
        global vmware_query
        vmware_query = results


@pytest.mark.parametrize('dkey', ['memory'])
def test_10_look_vm_query_(dkey):
    if nested_vm is False:
        pytest.skip(message)
    else:
        assert vmware_query.json()[0][dkey] == payload[dkey], vmware_query.text


def test_11_delete_vm(data):
    if nested_vm is False:
        pytest.skip(message)
    else:
        results = DELETE(f'/vm/id/{data["vmid"]}/')
        assert results.status_code == 200, results.text
