#!/usr/bin/env python3

# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from pytest_dependency import depends
from functions import DELETE, GET, POST, PUT
from auto_config import dev_test

from middlewared.test.integration.utils import call, ssh

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')
variable = 'aa.22'

TUNABLES_TO_SET = {}
SYSTEM_DEFAULT_TUNABLES = {}
TUNABLES_DB = {}
COMMENT = 'Test Comment'


@pytest.mark.dependency(name='GENERATE_TUNABLES_INFO')
def test_01_generating_tunables_information():
    global TUNABLES_TO_SET
    TUNABLES_TO_SET = {}
    for iface in call('interface.query'):
        tunable = f'net.ipv4.conf.{iface["name"]}.log_martians'
        TUNABLES_TO_SET[tunable] = '1'


@pytest.mark.dependency(name='CREATE_TUNABLES')
def test_02_creating_test_tunables(request):
    depends(request, ['GENERATE_TUNABLES_INFO'])
    global TUNABLES_DB
    for tunable, value in TUNABLES_TO_SET.items():
        payload = {'var': tunable, 'value': value, 'type': 'SYSCTL', 'comment': COMMENT}
        results = POST('/tunable/', payload)
        assert results.status_code == 200, results.text

        db_info = results.json()
        TUNABLES_DB[db_info['id']] = db_info


@pytest.mark.dependency(name='VALIDATE_DB_INFO')
def test_03_validating_tunables_database_info(request):
    depends(request, ['CREATE_TUNABLES'])
    for _id, _ in TUNABLES_DB.items():
        results = GET(f'/tunable/?id={_id}')
        assert results.status_code == 200, results.text
        assert results.json()[0] == TUNABLES_DB[_id], results.text


@pytest.mark.dependency(name='VALIDATE_CREATED_TUNABLES')
def test_04_validating_created_tunables_values_match_kernel_values(request):
    depends(request, ['VALIDATE_DB_INFO'])
    for tunable, value in TUNABLES_TO_SET.items():
        assert ssh(f'sysctl -n {tunable}').strip() == value


@pytest.mark.dependency(name='DISABLE_TUNABLES')
def test_05_disabling_test_tunables(request):
    depends(request, ['VALIDATE_CREATED_TUNABLES'])
    for _id, _ in TUNABLES_DB.items():
        results = PUT(f'/tunable/id/{_id}/', {'enabled': False})
        assert results.status_code == 200, results.text
        assert results.json()['enabled'] is False, results.text


@pytest.mark.dependency(name='VALIDATE_DISABLED_TUNABLES')
def test_06_validating_disabled_tunables_values_match_kernel_default_values(request):
    depends(request, ['DISABLE_TUNABLES'])
    for _id, info in TUNABLES_DB.items():
        assert ssh(f'sysctl -n {info["var"]}').strip() == info['orig_value']


@pytest.mark.dependency(name='DELETE_ALL_TUNABLES')
def test_07_deleting_all_test_tunables(request):
    depends(request, ['VALIDATE_DISABLED_TUNABLES'])
    for _id, _ in TUNABLES_DB.items():
        results = DELETE(f'/tunable/id/{_id}/', None)
        assert results.status_code == 200, results.text


def test_08_validating_all_tunables_were_deleted(request):
    depends(request, ['DELETE_ALL_TUNABLES'])
    for _id, _ in TUNABLES_DB.items():
        results = GET(f'/tunable/?id={_id}')
        assert results.status_code == 200, results.text
        assert not results.json()
