#!/usr/bin/env python3

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, PUT
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

all_services = {i['service']: i for i in GET('/service').json()}

@pytest.mark.dependency(name='ENABLE')
@pytest.mark.parametrize('svc', list(all_services.keys()))
def test_01_enable_service(svc):
    results = PUT(f'/service/id/{all_services[svc]["id"]}/', {'enable': True})
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name='VERIFY_ENABLE')
@pytest.mark.parametrize('svc', list(all_services.keys()))
def test_02_verify_service_was_enabled(svc, request):
    depends(request, ['ENABLE'])
    results = GET(f'/service/id/{all_services[svc]["id"]}/')
    assert results.status_code == 200, results.text
    assert results.json()['enable'], results.text


@pytest.mark.dependency(name='DISABLE')
@pytest.mark.parametrize('svc', list(all_services.keys()))
def test_03_disable_service(svc, request):
    depends(request, ['VERIFY_ENABLE'])
    results = PUT(f'/service/id/{all_services[svc]["id"]}/', {'enable': False})
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('svc', list(all_services.keys()))
def test_04_verify_service_was_disabled(svc, request):
    depends(request, ['DISABLE'])
    results = GET(f'/service/id/{all_services[svc]["id"]}/')
    assert results.status_code == 200, results.text
    assert not results.json()['enable'], results.text
