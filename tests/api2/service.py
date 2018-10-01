#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT


services = ['afp', 'cifs', 'nfs', 'snmp', 'tftp', 'webdav', 'lldp']
all_service = GET('/service/').json()


def test_01_service_query():
    results = GET('/service/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True


@pytest.mark.parametrize('svc', all_service)
def test_02_service_update(svc):
    results = PUT(f'/service/id/{svc["id"]}', {'enable': svc['enable']})
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('svc', services)
def test_03_start_service(svc):
    results = POST('/service/start/', {'service': svc})
    assert results.status_code == 200, results.text
    assert results.json() is True


@pytest.mark.parametrize('svc', services)
def test_04_service_stop(svc):
    results = POST('/service/stop/', {'service': svc})
    assert results.status_code == 200, results.text
    assert results.json() is False
