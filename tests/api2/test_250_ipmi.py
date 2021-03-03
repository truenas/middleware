#!/usr/bin/env python3

# License: BSD

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT, SSH_TEST
from auto_config import ip, user, password, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

global IPMI_LOADED


def test_01_ipmi_endpoint_working():
    result = GET('/ipmi/')
    assert result.status_code == 200, result.text


def test_02_ipmi_query_call():
    result = GET('/ipmi/')
    assert isinstance(result.json(), list), result.text


def test_03_ipmi_channel_call():
    result = GET('/ipmi/channels/')
    assert isinstance(result.json(), list), result.text


def test_04_ipmi_is_loaded():
    global IPMI_LOADED
    result = GET('/ipmi/is_loaded/')
    IPMI_LOADED = result.json()
    assert isinstance(result.json(), bool), result.text


def test_05_ipmi_identify_call():
    if IPMI_LOADED:
        result = POST('/ipmi/identify/', {'seconds': 2})
        assert result.status_code == 200, result.text


def test_06_update_ipmi_interface():
    if IPMI_LOADED:
        channel = GET('/ipmi/channels/').json()[0]
        result = PUT(
            f'/ipmi/id/{channel}/', {
                'ipaddress': '10.20.21.115',
                'netmask': '23',
                'gateway': '10.20.20.1',
                'password': 'abcd1234'
            }
        )
        assert result.status_code == 200, result.text


def test_07_verify_ipmi_channels_do_not_leak_password_in_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "abcd1234" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])
