#!/usr/bin/env python3

# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, PUT
from auto_config import scale, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')
variable = 'aa.22'
type1 = 'SYSCTL' if scale else 'RC'


def test_01_creating_test_tunable():
    global TUNABLE_ID, payload, results
    payload = {
        'var': variable,
        'value': 'test',
        'type': 'SYSCTL',
        'enabled': True
    }
    results = POST('/tunable/', payload)
    assert results.status_code == 200, results.text
    TUNABLE_ID = results.json()['id']


@pytest.mark.parametrize('tun', ['var', 'value', 'type', 'enabled'])
def test_02_looking_at_tunable_created_object_(tun):
    assert results.json()[tun] == payload[tun], results.text


@pytest.mark.parametrize('tun', ['var', 'value', 'type', 'enabled'])
def test_03_looking_at_tunable_search_id_object_(tun):
    results = GET(f'/tunable/?id={TUNABLE_ID}')
    assert results.status_code == 200, results.text
    assert results.json()[0][tun] == payload[tun], results.text


@pytest.mark.parametrize('tun', ['var', 'value', 'type', 'enabled'])
def test_04_looking_at_tunable_id_object_(tun):
    results = GET(f'/tunable/id/{TUNABLE_ID}/')
    assert results.status_code == 200, results.text
    assert results.json()[tun] == payload[tun], results.text


def test_05_disable_tuneable():
    results = PUT(f'/tunable/id/{TUNABLE_ID}/', {'enabled': False})
    assert results.status_code == 200, results.text
    assert results.json()['enabled'] is False, results.text


def test_06_looking_if_tunable_id_disable():
    results = GET(f'/tunable/id/{TUNABLE_ID}/')
    assert results.status_code == 200, results.text
    assert results.json()['enabled'] is False, results.text


def test_07_updating_variable_name_value_comment_type():
    global payload, results
    payload = {
        'var': variable + '1',
        'value': 'temp',
        'comment': 'testing variable',
        'type': type1,
        'enabled': True
    }

    results = PUT(f'/tunable/id/{TUNABLE_ID}/', payload)
    assert results.status_code == 200, results.text
    j_resp = results.json()
    payload['id'] = TUNABLE_ID

    assert j_resp == payload, results.text


@pytest.mark.parametrize('tun', ['var', 'value', 'comment', 'type', 'enabled'])
def test_08_looking_at_tunable_updated_object_(tun):
    assert results.json()[tun] == payload[tun], results.text


@pytest.mark.parametrize('tun', ['var', 'value', 'comment', 'type', 'enabled'])
def test_09_looking_at_tunable_id_object_(tun):
    results = GET(f'/tunable/id/{TUNABLE_ID}/')
    assert results.status_code == 200, results.text
    assert results.json()[tun] == payload[tun], results.text


def test_10_deleting_tunable():
    results = DELETE(f'/tunable/id/{TUNABLE_ID}/', None)
    assert results.status_code == 200, results.text


def test_11_ensure_tunalbe_deleted_id_is_not_searchable():
    results = GET(f'/tunable/?id={TUNABLE_ID}')
    assert results.status_code == 200, results.text
    assert results.json() == [], results.text


def test_12_ensure_tunnable_does_not_exist():
    results = GET(f'/tunable/id/{TUNABLE_ID}/')
    assert results.status_code == 404, results.text
