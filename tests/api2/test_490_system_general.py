#!/usr/bin/env python3
# License: BSD

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, SSH_TEST
from auto_config import user, password, ip, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')
TIMEZONE = "America/New_York"
SYSLOGLEVEL = "F_CRIT"


def test_01_get_system_general():
    results = GET("/system/general/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict)


def test_02_get_system_general_language_choices():
    results = GET("/system/general/language_choices/")
    assert results.status_code == 200, results.text
    data = results.json()
    assert isinstance(data, dict), data


def test_03_get_system_general_timezone_choices():
    results = GET("/system/general/timezone_choices/")
    assert results.status_code == 200, results.text
    data = results.json()
    assert isinstance(data, dict), data
    assert TIMEZONE in data


def test_04_get_system_general_country_choices():
    results = GET("/system/general/country_choices/")
    assert results.status_code == 200, results.text
    data = results.json()
    assert isinstance(data, dict), data


def test_05_get_system_general_kbdmap_choices():
    results = GET("/system/general/kbdmap_choices/")
    assert results.status_code == 200, results.text
    data = results.json()
    assert isinstance(data, dict), data


def test_06_Setting_timezone():
    results = PUT("/system/general/", {"timezone": TIMEZONE})
    assert results.status_code == 200, results.text


def test_07_Checking_timezone_using_api():
    results = GET("/system/general/")
    assert results.status_code == 200, results.text
    data = results.json()
    assert data['timezone'] == TIMEZONE


def test_08_Checking_timezone_using_ssh(request):
    depends(request, ["ssh_password"], scope="session")
    results = SSH_TEST(f'diff /etc/localtime /usr/share/zoneinfo/{TIMEZONE}',
                       user, password, ip)
    assert results['result'] is True, results


def test_09_Setting_sysloglevel():
    results = PUT("/system/general/", {"sysloglevel": SYSLOGLEVEL})
    assert results.status_code == 200, results.text


def test_10_Checking_sysloglevel_using_api():
    results = GET("/system/advanced/")
    assert results.status_code == 200, results.text
    data = results.json()
    assert data['sysloglevel'] == SYSLOGLEVEL
