#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT, DELETE


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


def test_03_vm_query():
    results = GET('/vm/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True


@pytest.mark.skip('Not working in Bhyve')
def test_04_start_vm(data):
    results = POST(f'/vm/id/{data["vmid"]}/start/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True


def test_05_vm_status(data):
    results = POST(f'/vm/id/{data["vmid"]}/status/')
    assert results.status_code == 200, results.text
    status = results.json()
    assert isinstance(status, dict) is True


def test_06_stop_vm(data):
    results = POST(f'/vm/id/{data["vmid"]}/stop/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True


def test_07_update_vm(data):
    payload = {
        'memory': 1100,
    }
    results = PUT(f'/vm/id/{data["vmid"]}/', payload)
    assert results.status_code == 200, results.text
    assert GET(f'/vm?id={data["vmid"]}').json()[0]['memory'] == 1100


def test_08_delete_vm(data):
    results = DELETE(f'/vm/id/{data["vmid"]}/')
    assert results.status_code == 200, results.text
