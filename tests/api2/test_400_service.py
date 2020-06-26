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
from auto_config import ha


services = ['afp', 'cifs', 'nfs', 'snmp', 'tftp', 'webdav', 'lldp']
all_service = GET('/service/', controller_a=ha).json()


def test_01_service_query():
    results = GET('/service/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True


@pytest.mark.parametrize('svc', all_service)
def test_02_service_update(svc):
    results = PUT(f'/service/id/{svc["id"]}', {'enable': svc['enable']})
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('svc', all_service)
def test_03_looking_service_enable(svc):
    results = GET(f'/service/id/{svc["id"]}')
    assert results.status_code == 200, results.text
    assert results.json()['enable'] == svc['enable'], results.text


@pytest.mark.parametrize('svc', services)
def test_04_start_service(svc):
    results = POST('/service/start/', {'service': svc})
    assert results.status_code == 200, results.text
    assert results.json() is True
    sleep(1)


@pytest.mark.parametrize('svc', services)
def test_05_looking_if_service_is_running(svc):
    results = GET(f'/service/?service={svc}')
    assert results.status_code == 200, results.text
    assert results.json()[0]['state'] == 'RUNNING', results.text


@pytest.mark.parametrize('svc', services)
def test_06_service_stop(svc):
    results = POST('/service/stop/', {'service': svc})
    assert results.status_code == 200, results.text
    assert results.json() is False
    sleep(1)


@pytest.mark.parametrize('svc', services)
def test_05_looking_if_service_is_stopped(svc):
    results = GET(f'/service/?service={svc}')
    assert results.status_code == 200, results.text
    assert results.json()[0]['state'] == 'STOPPED', results.text
