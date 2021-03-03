#!/usr/bin/env python3
# License: BSD

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, POST, SSH_TEST
from auto_config import ip, password, user, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')
COMMUNITY = 'public'
TRAPS = False
CONTACT = 'root@localhost.com'
LOCATION = 'Maryville, TN'
PASSWORD = 'testing1234'


def test_01_Configure_SNMP():
    results = PUT('/snmp/', {
        'community': COMMUNITY,
        'traps': TRAPS,
        'contact': CONTACT,
        'location': LOCATION,
        'v3_password': PASSWORD})
    assert results.status_code == 200, results.text


def test_02_Enable_SNMP_service_at_boot():
    results = PUT('/service/id/snmp/', {'enable': True})
    assert results.status_code == 200, results.text


def test_03_verify_snmp_do_not_leak_password_in_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = f"""grep -R "{PASSWORD}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_04_checking_to_see_if_snmp_service_is_enabled_at_boot():
    results = GET("/service?service=snmp")
    assert results.json()[0]["enable"] is True, results.text


def test_05_starting_snmp_service():
    payload = {"service": "snmp"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text


def test_06_checking_to_see_if_snmp_service_is_running():
    results = GET("/service?service=snmp")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_07_Validate_that_SNMP_service_is_running():
    results = GET('/service?service=snmp')
    assert results.json()[0]['state'] == 'RUNNING', results.text


def test_08_Validate_that_SNMP_settings_are_preserved():
    results = GET('/snmp/')
    assert results.status_code == 200, results.text
    data = results.json()
    assert data['community'] == COMMUNITY
    assert data['traps'] == TRAPS
    assert data['contact'] == CONTACT
    assert data['location'] == LOCATION
    assert data['v3_password'] == PASSWORD
