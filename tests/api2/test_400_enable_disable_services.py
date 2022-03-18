#!/usr/bin/env python3

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, PUT
from auto_config import dev_test, ha
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

all_services = {i['service']: i for i in GET('/service', controller_a=ha).json()}
service_names = list(all_services.keys())


@pytest.mark.dependency(name='ENABLE')
@pytest.mark.parametrize('svc', service_names)
def test_01_enable_and_verify_service(svc):
    results = PUT(f'/service/id/{all_services[svc]["id"]}/', {'enable': True})
    assert results.status_code == 200, results.text

    results = GET(f'/service/id/{all_services[svc]["id"]}/')
    assert results.status_code == 200, results.text
    assert results.json()['enable'], results.text


@pytest.mark.parametrize('svc', service_names)
def test_02_disable_and_verify_service(svc, request):
    depends(request, ['ENABLE'])
    results = PUT(f'/service/id/{all_services[svc]["id"]}/', {'enable': False})
    assert results.status_code == 200, results.text

    results = GET(f'/service/id/{all_services[svc]["id"]}/')
    assert results.status_code == 200, results.text
    assert not results.json()['enable'], results.text
