#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET  # , POST
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


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


def test_04_check_system_is_freenas():
    results = GET("/system/is_freenas/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True, results.text


def test_05_check_system_debug():
    results = GET("/system/debug/")
    assert results.status_code == 200, results.text


# Reboot system to enable tunable
# def test_06_Reboot_system_to_enable_tunable():
#     assert POST("/system/reboot/") == 200
