#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
from configparser import ConfigParser
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, SSH_TEST
from auto_config import dev_test, user, password, ip
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


if os.path.exists(f'{apifolder}/config.cfg') is True:
    configs = ConfigParser()
    configs.read('config.cfg')
    version = configs['NAS_CONFIG']['version']

    # These folowing test will only run if iXautomation created config.cfg
    def test_06_verify_system_version_and_system_info_version_match_iso_version():
        system_version_results = GET("/system/version/")
        assert system_version_results.json() == version, system_version_results.text

        system_info_results = GET("/system/info/")
        assert system_info_results.json()['version'] == version, system_info_results.text

    def test_07_verify_etc_versionwith_iso_version():
        results = SSH_TEST('cat /etc/version', user, password, ip)
        assert results['result'] is True, f'out: {results["output"]}, err: {results["stderr"]}'
        assert version in results["output"], str(results["output"])
