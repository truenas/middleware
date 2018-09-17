#!/usr/bin/env python3.6
# License: BSD

import os
import sys

import pytest

apifolder = os.getcwd()
sys.path.append(apifolder)

from config import *
from functions import GET, POST, PUT

Reason = 'NOIPUSERNAME, NOIPPASSWORD and NOIPHOST' \
    ' are missing in ixautomation.conf'

noip_test_cfg = pytest.mark.skipif(all(['NOIPUSERNAME' in locals(),
                                        'NOIPPASSWORD' in locals(),
                                        'NOIPHOST' in locals()
                                        ]) is False, reason=Reason)
custom_test_cfg = pytest.mark.skipif(noip_test_cfg is True,
                                     reason='no-ip test has ran instead')
global test
test = ''


@noip_test_cfg
def test_01_Updating_Settings_for_NO_IP():
    global test

    results = PUT('/dyndns/', {
        'username': NOIPUSERNAME,
        'password': NOIPPASSWORD,
        'provider': 'default@no-ip.com',
        'domain': NOIPHOST})
    assert results.status_code == 200, results.text
    test = 'NOIP'


@custom_test_cfg
def test_01_Updating_Settings_for_Custom_Provider():
    global test
    results = PUT('/dyndns/', {
        'username': 'foo',
        'password': 'bar',
        'provider': 'ixsystems.com',
        'domain': ['foobar']})
    assert results.status_code == 200, results.text
    test = 'CUSTOM'


def test_02_Check_that_API_reports_dyndns_service():
    results = GET('/dyndns/')
    assert results.status_code == 200, results.text


def test_03_Check_that_API_reports_dynsdns_configuration_as_saved():
    results = GET('/dyndns/')
    assert results.status_code == 200, results.text
    data = results.json()
    if test == 'NOIP':
        assert data['username'] == NOIPPASSWORD
        assert data['provider'] == 'default@no-ip.com'
        assert data['domain'] == NOIPHOST
    else:
        assert data['username'] == 'foo'
        assert data['provider'] == 'ixsystems.com'
        assert data['domain'] == ['foobar']


def test_04_Enable_dyns_service():
    results = PUT('/service/id/dynamicdns/', {'enable': True})
    assert results.status_code == 200, results.text


def test_04_Check_to_see_if_dyndns_service_is_enabled_at_boot():
    results = GET('/service?service=dynamicdns')
    assert results.json()[0]['enable'] is True, results.text


@noip_test_cfg
def test_05_Starting_dyndns_service():
    results = POST('/service/start/',
                   {'service': 'dynamicdns',
                    'service-control': {'onetime': True}})
    assert results.status_code == 200, results.text


@noip_test_cfg
def test_05_Checking_to_see_if_dyndns_service_is_running():
    results = GET('/service?service=dynamicdns')
    assert results.json()[0]['state'] == 'RUNNING', results.text
