#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT
from auto_config import ha, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

services = ['afp', 'cifs', 'nfs', 'snmp', 'tftp', 'webdav', 'lldp']

all_services = []
for service in GET('/service/', controller_a=ha).json():
    all_services.append(service['id'])


@pytest.fixture(scope='module')
def services_list():
    return {}


def test_01_service_query():
    results = GET('/service/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True


@pytest.mark.parametrize('svc', all_services)
def test_02_get_service_info_for(svc, services_list):
    results = GET(f'/service/id/{svc}/')
    assert results.status_code == 200, results.text
    services_list[svc] = results.json()


@pytest.mark.parametrize('svc', all_services)
def test_03_service_update(svc, services_list):
    payload = {'enable': services_list[svc]['enable']}
    results = PUT(f'/service/id/{svc}/', payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('svc', all_services)
def test_04_looking_service_enable(svc, services_list):
    results = GET(f'/service/id/{svc}/')
    assert results.status_code == 200, results.text
    assert results.json()['enable'] == services_list[svc]['enable'], results.text


@pytest.mark.parametrize('svc', services)
def test_05_start_service(svc):
    results = POST('/service/start/', {'service': svc})
    assert results.status_code == 200, results.text
    assert results.json() is True
    sleep(1)


@pytest.mark.parametrize('svc', services)
def test_06_looking_if_service_is_running(svc):
    results = GET(f'/service/?service={svc}')
    assert results.status_code == 200, results.text
    assert results.json()[0]['state'] == 'RUNNING', results.text


@pytest.mark.parametrize('svc', services)
def test_07_service_stop(svc):
    results = POST('/service/stop/', {'service': svc})
    assert results.status_code == 200, results.text
    assert results.json() is False
    sleep(1)


@pytest.mark.parametrize('svc', services)
def test_08_looking_if_service_is_stopped(svc):
    results = GET(f'/service/?service={svc}')
    assert results.status_code == 200, results.text
    assert results.json()[0]['state'] == 'STOPPED', results.text
