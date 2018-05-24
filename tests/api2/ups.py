#!/usr/bin/env python3.6
# License: BSD

import os
import sys

from functions import GET, PUT

apifolder = os.getcwd()
sys.path.append(apifolder)


def test_01_Enabling_UPS_Service():
    results = PUT('/service/id/ups', {'enable': True})
    assert results.status_code == 200, results.text


def test_10_Disabling_UPS_Service():
    results = PUT('/service/id/ups', {'enable': False})
    assert results.status_code == 200, results.text


def test_02_Set_UPS_options():
    results = PUT('/ups', {
        'rmonitor': True,
        'emailnotify': True,
        'mode': 'MASTER',
        'shutdown': 'BATT',
        'port': '655',
        'remotehost': '127.0.0.1',
        'identifier': 'ups'
        })
    assert results.status_code == 200, results.text


def test_03_Checking_that_API_reports_UPS_configuration_as_saved():
    results = GET('/ups')
    assert results.status_code == 200, results.text
    data = results.json()
    assert data['rmonitor'] is True
    assert data['emailnotify'] is True
    assert data['mode'] == 'MASTER'
    assert data['shutdown'] == 'BATT'
    assert data['port'] == '655'
    assert data['remotehost'] == '127.0.0.1'
    assert data['identifier'] == 'ups'


def test_03_Change_UPS_options():
    results = PUT('/ups', {
        'rmonitor': False,
        'emailnotify': False,
        'mode': 'SLAVE',
        'shutdown': 'LOWBATT',
        'port': '65535',
        'identifier': 'foo'
        })
    assert results.status_code == 200, results.text


def test_03_Checking_that_API_reports_UPS_configuration_as_changed():
    results = GET('/ups')
    assert results.status_code == 200, results.text
    data = results.json()
    assert data['rmonitor'] is False
    assert data['emailnotify'] is False
    assert data['mode'] == 'SLAVE'
    assert data['shutdown'] == 'LOWBATT'
    assert data['port'] == '65535'
    assert data['identifier'] == 'foo'
