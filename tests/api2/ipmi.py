#!/usr/bin/env python3.6

# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT


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
                'password': 'test'
            }
        )
        assert result.status_code == 200, result.text
