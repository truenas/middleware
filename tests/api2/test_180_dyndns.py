#!/usr/bin/env python3
# License: BSD

import os
import sys
import pytest
from time import sleep
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from config import *
from auto_config import ip, user, password, dev_test
from functions import GET, POST, PUT, SSH_TEST
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

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


def test_01_get_dyndns_provider_choices():
    results = GET('/dyndns/provider_choices/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    assert results.json()['default@dyndns.org'] == 'dyndns.org', results.text


def test_02_Updating_Settings_with_a_not_supported_provider_expect_422():
    global test
    results = PUT('/dyndns/', {
        'provider': 'ixsystems.com'})
    assert results.status_code == 422, results.text


@noip_test_cfg
def test_03_Updating_Settings_for_NO_IP():
    global test
    results = PUT('/dyndns/', {
        'username': NOIPUSERNAME,
        'password': NOIPPASSWORD,
        'provider': 'default@no-ip.com',
        'domain': NOIPHOST})
    assert results.status_code == 200, results.text
    test = 'NOIP'


@custom_test_cfg
def test_04_Updating_Settings_for_Custom_Provider():
    global test
    results = PUT('/dyndns/', {
        'username': 'foo',
        'password': 'abcd1234',
        'provider': 'default@dyndns.org',
        'domain': ['foobar']})
    assert results.status_code == 200, results.text
    test = 'CUSTOM'


def test_05_Check_that_API_reports_dyndns_service():
    results = GET('/dyndns/')
    assert results.status_code == 200, results.text


def test_06_verify_dyndhs_do_not_leak_password_in_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    if noip_test_cfg is True:
        cmd = f"""grep -R "{NOIPPASSWORD}" /var/log/middlewared.log"""
    else:
        cmd = """grep -R "abcd1234" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_07_Check_that_API_reports_dynsdns_configuration_as_saved():
    results = GET('/dyndns/')
    assert results.status_code == 200, results.text
    data = results.json()
    if test == 'NOIP':
        assert data['username'] == NOIPPASSWORD
        assert data['provider'] == 'default@no-ip.com'
        assert data['domain'] == NOIPHOST
    else:
        assert data['username'] == 'foo'
        assert data['provider'] == 'default@dyndns.org'
        assert data['domain'] == ['foobar']


def test_08_Enable_dyns_service():
    results = PUT('/service/id/dynamicdns/', {'enable': True})
    assert results.status_code == 200, results.text


def test_09_Check_to_see_if_dyndns_service_is_enabled_at_boot():
    results = GET('/service?service=dynamicdns')
    assert results.json()[0]['enable'] is True, results.text


@noip_test_cfg
def test_10_Starting_dyndns_service():
    results = POST('/service/start/',
                   {'service': 'dynamicdns'})
    assert results.status_code == 200, results.text
    sleep(1)


@noip_test_cfg
def test_11_Checking_to_see_if_dyndns_service_is_running():
    results = GET('/service?service=dynamicdns')
    assert results.json()[0]['state'] == 'RUNNING', results.text
