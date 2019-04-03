#!/usr/bin/env python3.6
# License: BSD

import pytest
import os
import sys
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, PUT

ups_dc_list = list(GET('/ups/driver_choices/').json().keys())

first_ups_list = [
    'rmonitor',
    'emailnotify',
    'mode',
    'shutdown',
    'port',
    'remotehost',
    'identifier',
    'driver'
]

second_ups_list = [
    'rmonitor',
    'emailnotify',
    'mode',
    'shutdown',
    'port',
    'identifier'
]


def test_01_Enabling_UPS_Service():
    results = PUT('/service/id/ups/', {'enable': True})
    assert results.status_code == 200, results.text


def test_02_Set_UPS_options():
    global payload, results
    payload = {
        'rmonitor': True,
        'emailnotify': True,
        'mode': 'MASTER',
        'shutdown': 'BATT',
        'port': '655',
        'remotehost': '127.0.0.1',
        'identifier': 'ups',
        'driver': 'usbhid-ups$PROTECT NAS'
    }
    results = PUT('/ups/', payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', first_ups_list)
def test_03_look_at_UPS_options_output_of_(data):
    assert payload[data] == results.json()[data], results.text


def test_04_get_API_reports_UPS_configuration_as_saved():
    global results
    results = GET('/ups/')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', first_ups_list)
def test_05_look_API_reports_UPS_configuration_of_(data):
    assert payload[data] == results.json()[data], results.text


def test_06_Change_UPS_options():
    global payload, results
    payload = {
        'rmonitor': False,
        'emailnotify': False,
        'mode': 'SLAVE',
        'shutdown': 'LOWBATT',
        'port': '65535',
        'identifier': 'foo'
    }
    results = PUT('/ups/', payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', second_ups_list)
def test_07_look_at_change_UPS_options_output_of_(data):
    assert payload[data] == results.json()[data], results.text


def test_08_get_API_reports_UPS_configuration_as_changed():
    global results
    results = GET('/ups/')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', second_ups_list)
def test_09_look_API_reports_UPS_configuration_of_(data):
    assert payload[data] == results.json()[data], results.text


def test_10_get_ups_driver_choice():
    results = GET('/ups/driver_choices/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    global ups_dc
    ups_dc = results


@pytest.mark.parametrize('dkey', ups_dc_list)
def test_11_check_ups_driver_choice_info_(dkey):
    driver_choices = dkey.partition('$')[2]
    assert isinstance(ups_dc.json()[dkey], str) is True, ups_dc.text
    assert driver_choices in ups_dc.json()[dkey], ups_dc.text


def test_12_get_ups_driver_choice():
    results = GET('/ups/port_choices/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    assert isinstance(results.json()[0], str) is True, results.text


def test_13_Disabling_UPS_Service():
    results = PUT('/service/id/ups/', {'enable': False})
    assert results.status_code == 200, results.text
