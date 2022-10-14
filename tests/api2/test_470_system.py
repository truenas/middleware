#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, make_ws_request # , POST
from auto_config import dev_test, ip
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


def test_01_check_if_system_is_ready_to_use():
    results = GET("/system/ready/")
    assert results.json() is True, results.text


def test_02_checking_system_version():
    results = GET("/system/version/")
    assert results.status_code == 200, results.text
    assert type(results.json()) == str, results.text


def test_03_check_system_version_match_with_system_info():
    system_version = GET("/system/info/").json()['version']
    system_info_version = GET("/system/version/").json()
    assert system_version == system_info_version


def test_04_check_system_product_type():
    results = GET("/system/product_type/")
    assert results.status_code == 200, results.text
    result = results.json()
    assert isinstance(result, str), results.text
    assert result in ('SCALE', 'SCALE_ENTERPRISE'), results.text


def test_05_check_system_debug():
    results = GET("/system/debug/")
    assert results.status_code == 200, results.text


def test_06_check_system_set_time():
    """
    This test intentionally slews our clock to be off
    by 300 seconds and then verifies that it got set
    """
    results = GET("/system/info/")
    assert results.status_code == 200, results.text

    # Convert to seconds
    datetime = results.json()['datetime']['$date']/1000

    # hop 300 seconds into the past
    target = datetime - 300
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'system.set_time',
        'params': [int(target)]
    })
    error = res.get('error')
    assert error is None, str(error)

    results = GET("/system/info/")
    assert results.status_code == 200, results.text
    datetime2 = results.json()['datetime']['$date']/1000

    # This is a fudge-factor because NTP will start working
    # pretty quickly to correct the slew.
    assert abs(target - datetime2) < 60
