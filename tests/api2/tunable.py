#!/usr/bin/env python3.6

# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, PUT

VARIABLE = 'aa.22'
TUNABLE_ID = 1


def test_01_creating_test_tunable():
    results = POST('/tunable/', {
        'var': VARIABLE,
        'value': 'test',
        'type': 'SYSCTL',
        'enabled': True
    })

    assert results.status_code == 200, results.text


def test_02_tunable_created_and_enabled():
    results = GET('/tunable/')

    assert results.json()[0]['enabled'], results.text


def test_03_retrieve_tunable_with_variable_name():
    results = GET(f'/tunable?var={VARIABLE}')

    assert results.json()[0]['var'] == VARIABLE, results.text


def test_04_disable_tuneable():
    results = PUT(f'/tunable/id/{TUNABLE_ID}/', {'enabled': False})
    assert results.json()['enabled'] is False, results.text


def test_05_updating_variable_name_value_comment_type():
    payload = {
        'var': VARIABLE + '1',
        'value': 'temp',
        'comment': 'testing variable',
        'type': 'RC',
        'enabled': True
    }

    results = PUT(
        f'/tunable/id/{TUNABLE_ID}/',
        payload
    )
    j_resp = results.json()
    payload['id'] = TUNABLE_ID

    assert j_resp == payload, results.text


def test_06_deleting_tunable():
    results = DELETE(
        f'/tunable/id/{TUNABLE_ID}/',
        None
    )

    assert results.status_code == 200, results.text


def test_07_ensure_API_has_no_tunables():
    results = GET('/tunable/')

    assert results.json() == [], results.text
