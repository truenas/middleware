#!/usr/bin/env python3
# License: BSD

import os
import pytest
import sys
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, POST, PUT, GET
from auto_config import interface, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

Reason = "VM detected no real ATA disk"

interface_exist = (interface == "vtnet0" or interface == "em0" or interface == 'enp0s7')
not_real_disk = pytest.mark.skipif(interface_exist, reason=Reason)


@pytest.fixture(scope='module')
def smart_dict():
    return {}


def test_01_create_a_new_smarttest(smart_dict):
    disks = GET('/disk/')
    assert disks.status_code == 200, disks.text
    disks = disks.json()
    assert isinstance(disks, list), disks
    assert len(disks) > 0, disks

    idents = smart_dict['idents'] = [d['identifier'] for d in disks]

    results = POST('/smart/test/', {
        'disks': idents,
        'type': 'LONG',
        'schedule': {
            'hour': '*',
            'dom': '*',
            'month': '*',
            'dow': '*',
        },
    })
    assert results.status_code == 200, results.text
    smart_dict['smarttest'] = results.json()


def test_02_check_that_API_reports_new_smarttest(smart_dict):
    results = GET(f'/smart/test/id/{smart_dict["smarttest"]["id"]}/')
    assert results.status_code == 200, results.text
    smarttest = results.json()
    assert isinstance(smarttest, dict), smarttest
    print(smarttest['disks'])
    for disk in smarttest['disks']:
        assert disk in smart_dict['idents']


def test_03_update_smarttest(smart_dict):
    results = PUT(f'/smart/test/id/{smart_dict["smarttest"]["id"]}/', {
        'type': 'SHORT',
    })
    assert results.status_code == 200, results.text


def test_04_delete_smarttest(smart_dict):
    results = DELETE(f'/smart/test/id/{smart_dict["smarttest"]["id"]}/')
    assert results.status_code == 200, results.text


def test_05_enable_smartd_service_at_boot():
    results = GET('/service/?service=smartd')
    smartid = results.json()[0]['id']

    results = PUT(f'/service/id/{smartid}/', {"enable": True})
    assert results.status_code == 200, results.text


def test_06_look_smartd_service_at_boot():
    results = GET('/service/?service=smartd')
    assert results.status_code == 200, results.text
    assert results.json()[0]["enable"] is True, results.text


@not_real_disk
def test_07_starting_smartd_service():
    payload = {"service": "smartd"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


@not_real_disk
def test_08_checking_to_see_if_smartd_service_is_running():
    results = GET('/service/?service=smartd')
    assert results.json()[0]["state"] == "RUNNING", results.text
