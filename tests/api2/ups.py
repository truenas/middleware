#!/usr/bin/env python3.6
# License: BSD

import pytest
import os
import sys
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, PUT

ups_dc_list = list(GET('/ups/driver_choices/').json().keys())


def test_01_Enabling_UPS_Service():
    results = PUT('/service/id/ups/', {'enable': True})
    assert results.status_code == 200, results.text


def test_02_Set_UPS_options():
    results = PUT('/ups/', {
        'rmonitor': True,
        'emailnotify': True,
        'mode': 'MASTER',
        'shutdown': 'BATT',
        'port': '655',
        'remotehost': '127.0.0.1',
        'identifier': 'ups'})
    assert results.status_code == 200, results.text


def test_03_Checking_that_API_reports_UPS_configuration_as_saved():
    results = GET('/ups/')
    assert results.status_code == 200, results.text
    data = results.json()
    assert data['rmonitor'] is True
    assert data['emailnotify'] is True
    assert data['mode'] == 'MASTER'
    assert data['shutdown'] == 'BATT'
    assert data['port'] == '655'
    assert data['remotehost'] == '127.0.0.1'
    assert data['identifier'] == 'ups'


def test_04_Change_UPS_options():
    results = PUT('/ups/', {
        'rmonitor': False,
        'emailnotify': False,
        'mode': 'SLAVE',
        'shutdown': 'LOWBATT',
        'port': '65535',
        'identifier': 'foo'})
    assert results.status_code == 200, results.text


def test_05_Checking_that_API_reports_UPS_configuration_as_changed():
    results = GET('/ups/')
    assert results.status_code == 200, results.text
    data = results.json()
    assert data['rmonitor'] is False
    assert data['emailnotify'] is False
    assert data['mode'] == 'SLAVE'
    assert data['shutdown'] == 'LOWBATT'
    assert data['port'] == '65535'
    assert data['identifier'] == 'foo'


def test_06_get_ups_driver_choice():
    results = GET('/ups/driver_choices/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    global ups_dc
    ups_dc = results


@pytest.mark.parametrize('dkey', ups_dc_list)
def test_07_check_ups_driver_choice_info_(dkey):
    driver_choices = dkey.partition('$')[2]
    assert isinstance(ups_dc.json()[dkey], str) is True, ups_dc.text
    assert driver_choices in ups_dc.json()[dkey], ups_dc.text


def test_08_get_ups_driver_choice():
    results = GET('/ups/port_choices/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    assert isinstance(results.json()[0], str) is True, results.text


def test_09_Disabling_UPS_Service():
    results = PUT('/service/id/ups/', {'enable': False})
    assert results.status_code == 200, results.text
